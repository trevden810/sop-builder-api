"""
Brand Management API Router
Handles logo upload and brand configuration
"""

import os
import json
import uuid
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import shutil

# Data models
class BrandConfig(BaseModel):
    primary_color: str = "#2C3E50"
    secondary_color: str = "#3498DB"
    accent_color: str = "#E74C3C"
    success_color: str = "#27AE60"
    warning_color: str = "#F39C12"
    company_name: str = "Your Company"
    tagline: str = "Professional SOP Solutions"
    logo_path: Optional[str] = None
    font_family: str = "Helvetica"
    footer_text: str = "Generated with AI-Enhanced SOP Builder"

class LogoUploadResponse(BaseModel):
    logo_url: str
    logo_path: str
    message: str

# Create router
router = APIRouter()

# Project paths
project_root = Path(__file__).parent.parent.parent
config_dir = project_root / "config"
uploads_dir = project_root / "uploads" / "logos"
brand_config_file = config_dir / "brand_config.json"

# Ensure directories exist
config_dir.mkdir(exist_ok=True)
uploads_dir.mkdir(parents=True, exist_ok=True)

class BrandService:
    """Service for brand management"""
    
    def __init__(self):
        self.allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg'}
        self.max_file_size = 5 * 1024 * 1024  # 5MB
    
    def load_brand_config(self) -> BrandConfig:
        """Load current brand configuration"""
        try:
            if brand_config_file.exists():
                with open(brand_config_file) as f:
                    config_data = json.load(f)
                return BrandConfig(**config_data)
            else:
                # Return default config
                return BrandConfig()
        except Exception as e:
            print(f"Error loading brand config: {e}")
            return BrandConfig()
    
    def save_brand_config(self, config: BrandConfig) -> bool:
        """Save brand configuration to file"""
        try:
            with open(brand_config_file, 'w') as f:
                json.dump(config.dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving brand config: {e}")
            return False
    
    def validate_logo_file(self, file: UploadFile) -> bool:
        """Validate uploaded logo file"""
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size (if available)
        if hasattr(file, 'size') and file.size > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB"
            )
        
        return True
    
    async def save_logo_file(self, file: UploadFile, company_id: str = "default") -> str:
        """Save uploaded logo file"""
        self.validate_logo_file(file)
        
        # Generate unique filename
        file_ext = Path(file.filename).suffix.lower()
        unique_filename = f"{company_id}_{uuid.uuid4().hex[:8]}{file_ext}"
        logo_path = uploads_dir / unique_filename
        
        # Save file
        try:
            with open(logo_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            return str(logo_path.relative_to(project_root))
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save logo: {str(e)}")

# Initialize service
brand_service = BrandService()

@router.get("/brand/config", response_model=BrandConfig)
async def get_brand_config():
    """Get current brand configuration"""
    return brand_service.load_brand_config()

@router.put("/brand/config", response_model=BrandConfig)
async def update_brand_config(config: BrandConfig):
    """Update brand configuration"""
    
    # Validate colors (basic hex color validation)
    color_fields = ['primary_color', 'secondary_color', 'accent_color', 'success_color', 'warning_color']
    for field in color_fields:
        color = getattr(config, field)
        if not color.startswith('#') or len(color) != 7:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid color format for {field}. Use hex format like #2C3E50"
            )
    
    # Validate company name
    if not config.company_name or len(config.company_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Company name must be at least 2 characters")
    
    # Save configuration
    if brand_service.save_brand_config(config):
        return config
    else:
        raise HTTPException(status_code=500, detail="Failed to save brand configuration")

@router.post("/brand/upload-logo", response_model=LogoUploadResponse)
async def upload_logo(
    logo_file: UploadFile = File(...),
    company_id: str = Form("default")
):
    """Upload company logo"""
    
    # Validate and save logo
    logo_path = await brand_service.save_logo_file(logo_file, company_id)
    
    # Update brand config with new logo path
    current_config = brand_service.load_brand_config()
    current_config.logo_path = logo_path
    
    if not brand_service.save_brand_config(current_config):
        raise HTTPException(status_code=500, detail="Failed to update brand configuration")
    
    # Generate URL for logo access
    logo_url = f"/api/v1/brand/logo/{Path(logo_path).name}"
    
    return LogoUploadResponse(
        logo_url=logo_url,
        logo_path=logo_path,
        message="Logo uploaded successfully"
    )

@router.get("/brand/logo/{filename}")
async def get_logo(filename: str):
    """Serve logo file"""
    logo_file = uploads_dir / filename
    
    if not logo_file.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")
    
    # Determine media type based on extension
    ext = logo_file.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.svg': 'image/svg+xml'
    }
    
    media_type = media_types.get(ext, 'application/octet-stream')
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(logo_file),
        media_type=media_type,
        filename=filename
    )

@router.delete("/brand/logo")
async def delete_logo():
    """Remove current logo"""
    
    # Load current config
    current_config = brand_service.load_brand_config()
    
    if current_config.logo_path:
        # Delete logo file
        logo_file = project_root / current_config.logo_path
        if logo_file.exists():
            try:
                logo_file.unlink()
            except Exception as e:
                print(f"Warning: Could not delete logo file: {e}")
        
        # Update config
        current_config.logo_path = None
        brand_service.save_brand_config(current_config)
    
    return {"message": "Logo removed successfully"}

@router.get("/brand/preview")
async def preview_brand_config():
    """Get brand configuration preview data"""
    config = brand_service.load_brand_config()
    
    # Generate preview data
    preview_data = {
        "config": config.dict(),
        "preview_elements": {
            "header_style": {
                "background_color": config.primary_color,
                "text_color": "#FFFFFF",
                "company_name": config.company_name,
                "tagline": config.tagline
            },
            "button_style": {
                "background_color": config.secondary_color,
                "text_color": "#FFFFFF"
            },
            "accent_elements": {
                "color": config.accent_color
            }
        }
    }
    
    return preview_data

@router.post("/brand/reset")
async def reset_brand_config():
    """Reset brand configuration to defaults"""
    
    default_config = BrandConfig()
    
    if brand_service.save_brand_config(default_config):
        return {
            "message": "Brand configuration reset to defaults",
            "config": default_config
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to reset brand configuration")
