"""
SOP Generation API Router
Integrates with existing SOP generator while providing async web interface
"""

import os
import sys
import uuid
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Add scripts directory to path for existing imports
project_root = Path(__file__).parent.parent.parent
scripts_path = project_root / "scripts"
sys.path.append(str(scripts_path))

# Import existing generators (preserve functionality)
try:
    from generators.sop_generator import SOPGenerator
    from utils.llm_client import FreeLLMClient
except ImportError as e:
    print(f"Warning: Could not import existing generators: {e}")
    # Create mock classes for development
    class SOPGenerator:
        def generate_sop(self, *args, **kwargs):
            return {"mock": "data"}
    
    class FreeLLMClient:
        def generate(self, *args, **kwargs):
            return type('obj', (object,), {'content': 'Mock content', 'provider': 'mock'})

# Data models
class CompanyInfo(BaseModel):
    name: str
    location: Optional[str] = None
    industry_specific: Optional[Dict[str, Any]] = {}

class BrandConfig(BaseModel):
    primary_color: Optional[str] = "#2C3E50"
    secondary_color: Optional[str] = "#3498DB"
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None

class Customization(BaseModel):
    selected_options: List[str] = []
    brand_config: Optional[BrandConfig] = None

class GenerationRequest(BaseModel):
    template_id: str
    company_info: CompanyInfo
    customization: Optional[Customization] = Customization()
    llm_provider: str = "automatic"
    output_format: str = "json"

class GenerationResponse(BaseModel):
    generation_id: str
    status: str
    estimated_completion: Optional[str] = None
    websocket_url: Optional[str] = None

class GenerationStatus(BaseModel):
    generation_id: str
    status: str  # pending, processing, completed, failed
    progress: int = 0
    current_step: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Create router
router = APIRouter()

# In-memory storage for generation jobs (will be replaced with database)
generation_jobs: Dict[str, GenerationStatus] = {}

class SOPGenerationService:
    """Service class that wraps existing SOP generator for async operation"""
    
    def __init__(self):
        self.sop_generator = SOPGenerator()
        self.llm_client = FreeLLMClient()
    
    async def generate_sop_async(self, request: GenerationRequest, generation_id: str):
        """Generate SOP asynchronously using existing generator"""
        try:
            # Update status to processing
            generation_jobs[generation_id].status = "processing"
            generation_jobs[generation_id].progress = 10
            generation_jobs[generation_id].current_step = "Initializing generation..."
            
            # Prepare parameters for existing generator
            template_type = self.map_template_id_to_type(request.template_id)
            
            # Update progress
            generation_jobs[generation_id].progress = 30
            generation_jobs[generation_id].current_step = "Generating content with AI..."
            
            # Use existing SOP generator in thread pool to avoid blocking
            sop_result = await asyncio.to_thread(
                self.sop_generator.generate_sop,
                template_type,
                company_name=request.company_info.name,
                location=request.company_info.location or "",
                custom_options=request.customization.selected_options if request.customization else [],
                llm_provider=request.llm_provider
            )
            
            # Update progress
            generation_jobs[generation_id].progress = 70
            generation_jobs[generation_id].current_step = "Applying customizations..."
            
            # Apply brand customizations if provided
            if request.customization and request.customization.brand_config:
                sop_result = self.apply_brand_customizations(
                    sop_result, 
                    request.customization.brand_config
                )
            
            # Update progress
            generation_jobs[generation_id].progress = 90
            generation_jobs[generation_id].current_step = "Finalizing document..."
            
            # Save result and update status
            result = {
                "template_data": sop_result,
                "generation_metadata": {
                    "template_id": request.template_id,
                    "company_name": request.company_info.name,
                    "generated_at": datetime.utcnow().isoformat(),
                    "llm_provider": request.llm_provider
                }
            }
            
            generation_jobs[generation_id].status = "completed"
            generation_jobs[generation_id].progress = 100
            generation_jobs[generation_id].current_step = "Generation complete!"
            generation_jobs[generation_id].result = result
            
        except Exception as e:
            generation_jobs[generation_id].status = "failed"
            generation_jobs[generation_id].error = str(e)
            generation_jobs[generation_id].current_step = f"Generation failed: {str(e)}"
    
    def map_template_id_to_type(self, template_id: str) -> str:
        """Map frontend template ID to existing generator template type"""
        mapping = {
            "restaurant-opening": "restaurant",
            "restaurant-closing": "restaurant",
            "healthcare-patient-care": "healthcare",
            "it-onboarding": "it-onboarding"
        }
        return mapping.get(template_id, "restaurant")  # Default to restaurant
    
    def apply_brand_customizations(self, sop_result: Dict, brand_config: BrandConfig) -> Dict:
        """Apply brand customizations to SOP result"""
        if not isinstance(sop_result, dict):
            return sop_result
        
        # Apply brand configuration
        if "metadata" not in sop_result:
            sop_result["metadata"] = {}
        
        sop_result["metadata"]["brand_config"] = {
            "primary_color": brand_config.primary_color,
            "secondary_color": brand_config.secondary_color,
            "company_name": brand_config.company_name,
            "tagline": brand_config.tagline,
            "logo_url": brand_config.logo_url
        }
        
        return sop_result

# Initialize service
generation_service = SOPGenerationService()

@router.post("/generate", response_model=GenerationResponse)
async def start_generation(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Start SOP generation process"""
    
    # Validate template exists
    if request.template_id not in ["restaurant-opening", "restaurant-closing", "healthcare-patient-care", "it-onboarding"]:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    # Validate company name
    if not request.company_info.name or len(request.company_info.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Company name is required")
    
    # Generate unique ID for this generation
    generation_id = str(uuid.uuid4())
    
    # Create initial job status
    generation_jobs[generation_id] = GenerationStatus(
        generation_id=generation_id,
        status="pending",
        progress=0,
        current_step="Queued for generation..."
    )
    
    # Start background generation
    background_tasks.add_task(
        generation_service.generate_sop_async,
        request,
        generation_id
    )
    
    return GenerationResponse(
        generation_id=generation_id,
        status="pending",
        estimated_completion=(datetime.utcnow().isoformat()),
        websocket_url=f"/ws/generation/{generation_id}"  # Will implement WebSocket later
    )

@router.get("/generate/{generation_id}/status", response_model=GenerationStatus)
async def get_generation_status(generation_id: str):
    """Get current status of generation job"""
    
    if generation_id not in generation_jobs:
        raise HTTPException(status_code=404, detail="Generation job not found")
    
    return generation_jobs[generation_id]

@router.get("/generate/jobs", response_model=Dict[str, List[GenerationStatus]])
async def list_generation_jobs():
    """List all generation jobs (for debugging/monitoring)"""
    return {"jobs": list(generation_jobs.values())}

@router.delete("/generate/{generation_id}")
async def cancel_generation(generation_id: str):
    """Cancel a generation job"""
    
    if generation_id not in generation_jobs:
        raise HTTPException(status_code=404, detail="Generation job not found")
    
    job = generation_jobs[generation_id]
    if job.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed job")
    
    # Mark as cancelled
    job.status = "cancelled"
    job.current_step = "Generation cancelled by user"
    
    return {"message": "Generation cancelled successfully"}
