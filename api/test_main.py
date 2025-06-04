"""
Simple test version of FastAPI app to verify setup
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI application
app = FastAPI(
    title="SOP Builder MVP API - Test",
    description="Test version to verify setup",
    version="1.0.0"
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://nextlevelsbs.com",
    "https://www.nextlevelsbs.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SOP Builder MVP API is running!"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "API is operational"
    }

@app.get("/api/v1/templates")
async def get_templates():
    """Simple templates endpoint"""
    return {
        "templates": [
            {
                "id": "restaurant-opening",
                "title": "Restaurant Opening Procedures",
                "description": "Complete checklist for daily restaurant opening procedures",
                "industry": "restaurant",
                "icon": "🍽️"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
