"""
Document Management API Router
Handles PDF generation, storage, and retrieval
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
scripts_path = project_root / "scripts"
sys.path.append(str(scripts_path))

# Import existing PDF generator
try:
    from generators.pdf_generator import EnhancedSOPPDFGenerator
except ImportError as e:
    print(f"Warning: Could not import PDF generator: {e}")
    # Mock for development
    class EnhancedSOPPDFGenerator:
        def __init__(self, *args, **kwargs):
            pass
        def generate_enhanced_pdf(self, *args, **kwargs):
            return "mock_output.pdf"

# Data models
class Document(BaseModel):
    id: str
    title: str
    template_id: str
    created_at: str
    status: str
    file_size: Optional[int] = None
    download_count: int = 0

class DocumentList(BaseModel):
    documents: List[Document]
    pagination: Optional[Dict] = None

class PDFGenerationRequest(BaseModel):
    template_data: Dict
    brand_config: Optional[Dict] = None
    preview_mode: bool = False

# Create router
router = APIRouter()

# In-memory document storage (will be replaced with database)
documents_storage: Dict[str, Document] = {}

class DocumentService:
    """Service for document management and PDF generation"""
    
    def __init__(self):
        self.output_dir = project_root / "outputs" / "pdfs"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load brand config
        self.load_brand_config()
    
    def load_brand_config(self):
        """Load brand configuration from existing config file"""
        config_path = project_root / "config" / "brand_config.json"
        try:
            if config_path.exists():
                import json
                with open(config_path) as f:
                    self.default_brand_config = json.load(f)
            else:
                self.default_brand_config = {
                    "primary_color": "#2C3E50",
                    "secondary_color": "#3498DB",
                    "company_name": "Your Company",
                    "tagline": "Professional SOP Solutions"
                }
        except Exception as e:
            print(f"Warning: Could not load brand config: {e}")
            self.default_brand_config = {}
    
    async def generate_pdf_async(self, template_data: Dict, brand_config: Optional[Dict] = None) -> str:
        """Generate PDF using existing PDF generator"""
        try:
            # Use provided brand config or default
            config = brand_config or self.default_brand_config
            
            # Create PDF generator instance
            pdf_generator = EnhancedSOPPDFGenerator(config)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_name = template_data.get("company_name", "SOP").replace(" ", "_")
            filename = f"{company_name}_{timestamp}.pdf"
            output_path = self.output_dir / filename
            
            # Generate PDF in thread pool to avoid blocking
            pdf_path = await asyncio.to_thread(
                pdf_generator.generate_enhanced_pdf,
                template_data,
                str(output_path)
            )
            
            return str(pdf_path)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    async def generate_preview_async(self, template_data: Dict, brand_config: Optional[Dict] = None) -> str:
        """Generate PDF preview (base64 encoded)"""
        try:
            # Generate PDF first
            pdf_path = await self.generate_pdf_async(template_data, brand_config)
            
            # Convert to base64 for preview
            import base64
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            preview_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # Clean up temporary file if it's a preview
            if "preview" in str(pdf_path):
                os.remove(pdf_path)
            
            return preview_base64
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

# Initialize service
document_service = DocumentService()

@router.get("/documents", response_model=DocumentList)
async def list_documents(page: int = 1, per_page: int = 20):
    """List user's generated documents"""
    
    # For now, return all documents (will add user filtering with auth)
    documents = list(documents_storage.values())
    
    # Simple pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_docs = documents[start_idx:end_idx]
    
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": len(documents),
        "total_pages": (len(documents) + per_page - 1) // per_page
    }
    
    return DocumentList(documents=paginated_docs, pagination=pagination)

@router.post("/documents/generate-pdf")
async def generate_pdf_document(request: PDFGenerationRequest):
    """Generate PDF document from template data"""
    
    try:
        # Generate PDF
        pdf_path = await document_service.generate_pdf_async(
            request.template_data,
            request.brand_config
        )
        
        # Create document record
        document_id = str(uuid.uuid4())
        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        
        document = Document(
            id=document_id,
            title=f"{request.template_data.get('title', 'SOP Document')}",
            template_id=request.template_data.get('template_id', 'unknown'),
            created_at=datetime.utcnow().isoformat(),
            status="completed",
            file_size=file_size,
            download_count=0
        )
        
        documents_storage[document_id] = document
        
        return {
            "document_id": document_id,
            "download_url": f"/api/v1/documents/{document_id}/download",
            "preview_url": f"/api/v1/documents/{document_id}/preview",
            "file_size": file_size
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/preview")
async def generate_pdf_preview(request: PDFGenerationRequest):
    """Generate PDF preview (base64 encoded)"""
    
    try:
        preview_base64 = await document_service.generate_preview_async(
            request.template_data,
            request.brand_config
        )
        
        return {
            "preview_base64": preview_base64,
            "content_type": "application/pdf"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{document_id}")
async def get_document_info(document_id: str):
    """Get document information"""
    
    if document_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return documents_storage[document_id]

@router.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download PDF document"""
    
    if document_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    document = documents_storage[document_id]
    
    # Find the actual file (simplified for now)
    pdf_files = list(document_service.output_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Use the most recent file for now (will improve with proper file tracking)
    pdf_file = max(pdf_files, key=lambda f: f.stat().st_mtime)
    
    # Increment download count
    document.download_count += 1
    
    return FileResponse(
        path=str(pdf_file),
        filename=f"{document.title}.pdf",
        media_type="application/pdf"
    )

@router.get("/documents/{document_id}/preview")
async def preview_document(document_id: str):
    """Get PDF preview (base64 encoded)"""
    
    if document_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Find and encode the PDF file
    pdf_files = list(document_service.output_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    pdf_file = max(pdf_files, key=lambda f: f.stat().st_mtime)
    
    import base64
    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()
    
    preview_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    return {
        "preview_base64": preview_base64,
        "content_type": "application/pdf"
    }

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete document"""
    
    if document_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove from storage
    del documents_storage[document_id]
    
    # TODO: Also delete the actual PDF file
    
    return {"message": "Document deleted successfully"}
