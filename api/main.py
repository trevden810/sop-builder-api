"""
SOP Builder MVP - FastAPI Application Entry Point
Integrates React frontend with existing Python backend while preserving all functionality
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import routers (will be created incrementally)
from api.routers import templates, generation, documents, brand, compliance

# Create FastAPI application
app = FastAPI(
    title="SOP Builder MVP API",
    description="Professional SOP generation with AI and regulatory compliance",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration for development and production
origins = [
    "http://localhost:3000",  # React dev server
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8080",  # Current Vite dev server
    "https://nextlevelsbs.com",  # Production domain
    "https://www.nextlevelsbs.com"  # Production www domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(templates.router, prefix="/api/v1", tags=["templates"])
app.include_router(generation.router, prefix="/api/v1", tags=["generation"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(brand.router, prefix="/api/v1", tags=["brand"])
app.include_router(compliance.router, prefix="/api/v1", tags=["compliance"])

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "api": "operational",
            "llm_providers": "operational",
            "pdf_generation": "operational"
        }
    }

# Serve React frontend static files in production
frontend_dist = project_root / "sop-wizard-pro-main" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist / "assets")), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React frontend for all non-API routes"""
        # Don't serve frontend for API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # Serve index.html for all frontend routes (SPA routing)
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")

# Development server configuration
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
