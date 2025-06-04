"""
Template Management API Router
Provides endpoints for browsing and retrieving SOP templates
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Template data models
class TemplateOption(BaseModel):
    id: str
    label: str
    default: bool
    required: bool = False

class Template(BaseModel):
    id: str
    title: str
    description: str
    industry: str
    icon: str
    estimated_time: str
    compliance: List[str]
    custom_options: List[TemplateOption]

class TemplateDetail(Template):
    content_sections: List[str]
    regulatory_requirements: Dict[str, str]

class Industry(BaseModel):
    id: str
    name: str
    template_count: int
    compliance_standards: List[str]

# Create router
router = APIRouter()

# Template data cache (loaded from existing content structure)
_template_cache = {}
_industry_cache = {}

def load_template_data():
    """Load template data from existing content structure"""
    if _template_cache:
        return _template_cache
    
    # Define template configurations based on existing content
    templates = {
        "restaurant-opening": {
            "id": "restaurant-opening",
            "title": "Restaurant Opening Procedures",
            "description": "Complete checklist for daily restaurant opening procedures",
            "industry": "restaurant",
            "icon": "🍽️",
            "estimated_time": "2-3 minutes",
            "compliance": ["FDA Food Code", "HACCP", "ServSafe"],
            "custom_options": [
                {"id": "food-safety", "label": "Include Food Safety Protocols", "default": True},
                {"id": "haccp", "label": "Include HACCP Procedures", "default": True},
                {"id": "employee-training", "label": "Include Employee Training", "default": False},
                {"id": "cleaning-procedures", "label": "Include Cleaning Procedures", "default": True},
                {"id": "inventory-management", "label": "Include Inventory Management", "default": False}
            ],
            "content_sections": ["introduction", "procedures", "safety", "compliance"],
            "regulatory_requirements": {
                "fda_food_code": "2022 FDA Food Code Section 2-301.11",
                "haccp": "HACCP Principle 1-7 Implementation"
            }
        },
        "restaurant-closing": {
            "id": "restaurant-closing",
            "title": "Restaurant Closing Procedures",
            "description": "End-of-day safety and security protocols",
            "industry": "restaurant",
            "icon": "🔒",
            "estimated_time": "3-4 minutes",
            "compliance": ["FDA Food Code", "OSHA", "Local Health Dept"],
            "custom_options": [
                {"id": "security-checklist", "label": "Include Security Checklist", "default": True},
                {"id": "equipment-shutdown", "label": "Include Equipment Shutdown", "default": True},
                {"id": "cash-handling", "label": "Include Cash Handling Procedures", "default": False},
                {"id": "cleaning-schedule", "label": "Include Deep Cleaning Schedule", "default": True}
            ],
            "content_sections": ["introduction", "procedures", "security", "compliance"],
            "regulatory_requirements": {
                "fda_food_code": "2022 FDA Food Code Section 4-501.11",
                "osha": "OSHA General Duty Clause Section 5(a)(1)"
            }
        },
        "healthcare-patient-care": {
            "id": "healthcare-patient-care",
            "title": "Patient Care Protocols",
            "description": "HIPAA-compliant patient care procedures",
            "industry": "healthcare",
            "icon": "🏥",
            "estimated_time": "4-5 minutes",
            "compliance": ["HIPAA", "CDC Guidelines", "Joint Commission"],
            "custom_options": [
                {"id": "hipaa-privacy", "label": "Include HIPAA Privacy Procedures", "default": True},
                {"id": "infection-control", "label": "Include Infection Control", "default": True},
                {"id": "emergency-procedures", "label": "Include Emergency Procedures", "default": False},
                {"id": "documentation", "label": "Include Documentation Standards", "default": True}
            ],
            "content_sections": ["introduction", "procedures", "privacy", "compliance"],
            "regulatory_requirements": {
                "hipaa": "HIPAA Privacy Rule 45 CFR 164.502",
                "cdc": "CDC Infection Prevention Guidelines"
            }
        },
        "healthcare-patient-intake": {
            "id": "healthcare-patient-intake",
            "title": "Patient Intake Procedures",
            "description": "Comprehensive patient intake and registration procedures",
            "industry": "healthcare",
            "icon": "📋",
            "estimated_time": "3-4 minutes",
            "compliance": ["HIPAA", "Joint Commission", "CMS Guidelines"],
            "custom_options": [
                {"id": "hipaa-privacy", "label": "Include HIPAA Privacy Procedures", "default": True},
                {"id": "insurance-verification", "label": "Include Insurance Verification", "default": True},
                {"id": "medical-history", "label": "Include Medical History Collection", "default": True},
                {"id": "consent-forms", "label": "Include Consent Form Procedures", "default": True},
                {"id": "emergency-contacts", "label": "Include Emergency Contact Collection", "default": False}
            ],
            "content_sections": ["introduction", "intake_procedures", "documentation", "compliance"],
            "regulatory_requirements": {
                "hipaa": "HIPAA Privacy Rule 45 CFR 164.502",
                "joint_commission": "Joint Commission Patient Safety Standards",
                "cms": "CMS Conditions of Participation"
            }
        },
        "it-onboarding": {
            "id": "it-onboarding",
            "title": "IT Employee Onboarding",
            "description": "New employee technology setup and security procedures",
            "industry": "technology",
            "icon": "💻",
            "estimated_time": "5-6 minutes",
            "compliance": ["SOX", "GDPR", "Company Security Policy"],
            "custom_options": [
                {"id": "security-training", "label": "Include Security Training", "default": True},
                {"id": "equipment-setup", "label": "Include Equipment Setup", "default": True},
                {"id": "access-management", "label": "Include Access Management", "default": True},
                {"id": "compliance-training", "label": "Include Compliance Training", "default": False}
            ],
            "content_sections": ["introduction", "procedures", "security", "compliance"],
            "regulatory_requirements": {
                "sox": "Sarbanes-Oxley Act Section 404",
                "gdpr": "GDPR Article 32 Security Requirements"
            }
        }
    }
    
    _template_cache.update(templates)
    return _template_cache

def load_industry_data():
    """Load industry data"""
    if _industry_cache:
        return _industry_cache
    
    industries = {
        "restaurant": {
            "id": "restaurant",
            "name": "Restaurant & Food Service",
            "template_count": 2,
            "compliance_standards": ["FDA Food Code", "HACCP", "ServSafe", "OSHA"]
        },
        "healthcare": {
            "id": "healthcare",
            "name": "Healthcare & Medical",
            "template_count": 2,
            "compliance_standards": ["HIPAA", "CDC Guidelines", "Joint Commission", "CMS", "OSHA"]
        },
        "technology": {
            "id": "technology",
            "name": "Information Technology",
            "template_count": 1,
            "compliance_standards": ["SOX", "GDPR", "ISO 27001", "NIST"]
        }
    }
    
    _industry_cache.update(industries)
    return _industry_cache

@router.get("/templates", response_model=Dict[str, List[Template]])
async def get_templates(industry: Optional[str] = Query(None, description="Filter by industry")):
    """Get available SOP templates, optionally filtered by industry"""
    templates_data = load_template_data()
    
    # Convert to Template models
    templates = []
    for template_data in templates_data.values():
        if industry and template_data["industry"] != industry:
            continue
            
        template = Template(
            id=template_data["id"],
            title=template_data["title"],
            description=template_data["description"],
            industry=template_data["industry"],
            icon=template_data["icon"],
            estimated_time=template_data["estimated_time"],
            compliance=template_data["compliance"],
            custom_options=[
                TemplateOption(**option) for option in template_data["custom_options"]
            ]
        )
        templates.append(template)
    
    return {"templates": templates}

@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def get_template_by_id(template_id: str):
    """Get specific template details"""
    templates_data = load_template_data()
    
    if template_id not in templates_data:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template_data = templates_data[template_id]
    
    return TemplateDetail(
        id=template_data["id"],
        title=template_data["title"],
        description=template_data["description"],
        industry=template_data["industry"],
        icon=template_data["icon"],
        estimated_time=template_data["estimated_time"],
        compliance=template_data["compliance"],
        custom_options=[
            TemplateOption(**option) for option in template_data["custom_options"]
        ],
        content_sections=template_data["content_sections"],
        regulatory_requirements=template_data["regulatory_requirements"]
    )

@router.get("/industries", response_model=Dict[str, List[Industry]])
async def get_industries():
    """Get available industries"""
    industries_data = load_industry_data()
    
    industries = [
        Industry(**industry_data) for industry_data in industries_data.values()
    ]
    
    return {"industries": industries}

@router.get("/industries/{industry_id}/templates", response_model=Dict[str, List[Template]])
async def get_templates_by_industry(industry_id: str):
    """Get templates for specific industry"""
    return await get_templates(industry=industry_id)
