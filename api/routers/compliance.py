"""
Compliance Validation API Router
Handles regulatory compliance checking and validation
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Data models
class RegulatoryRequirement(BaseModel):
    regulation: str
    section: str
    requirement: str
    citation_url: Optional[str] = None

class ComplianceValidationRequest(BaseModel):
    template_data: Dict
    industry: str
    regulations: List[str]

class ComplianceValidationResult(BaseModel):
    compliant: bool
    missing_requirements: List[str]
    recommendations: List[str]
    regulatory_citations: List[RegulatoryRequirement]
    compliance_score: float

class ComplianceStandard(BaseModel):
    id: str
    name: str
    description: str
    industry: str
    requirements: List[str]

# Create router
router = APIRouter()

# Project paths
project_root = Path(__file__).parent.parent.parent
compliance_data_dir = project_root / "data" / "compliance"

class ComplianceService:
    """Service for regulatory compliance validation"""
    
    def __init__(self):
        self.compliance_data = self.load_compliance_data()
    
    def load_compliance_data(self) -> Dict:
        """Load compliance data from YAML files"""
        compliance_data = {}
        
        # Load existing compliance data files
        if compliance_data_dir.exists():
            for yaml_file in compliance_data_dir.glob("*.yaml"):
                try:
                    with open(yaml_file) as f:
                        data = yaml.safe_load(f)
                        industry = yaml_file.stem
                        compliance_data[industry] = data
                except Exception as e:
                    print(f"Warning: Could not load {yaml_file}: {e}")
        
        # Add default compliance data if none exists
        if not compliance_data:
            compliance_data = self.get_default_compliance_data()
        
        return compliance_data
    
    def get_default_compliance_data(self) -> Dict:
        """Get default compliance data for supported industries"""
        return {
            "restaurant": {
                "standards": [
                    "FDA Food Code",
                    "HACCP",
                    "ServSafe",
                    "OSHA"
                ],
                "regulatory_links": {
                    "FDA": "https://www.fda.gov/food/fda-food-code",
                    "HACCP": "https://www.fda.gov/food/hazard-analysis-critical-control-point-haccp",
                    "OSHA": "https://www.osha.gov/restaurants"
                },
                "requirements": {
                    "FDA_FOOD_CODE": [
                        "Hand washing procedures (2-301.11)",
                        "Temperature monitoring (3-501.16)",
                        "Allergen management (2-301.11)",
                        "Cleaning and sanitizing (4-501.11)"
                    ],
                    "HACCP": [
                        "Hazard analysis",
                        "Critical control points",
                        "Critical limits",
                        "Monitoring procedures",
                        "Corrective actions",
                        "Verification",
                        "Record keeping"
                    ]
                }
            },
            "healthcare": {
                "standards": [
                    "HIPAA",
                    "CDC Guidelines",
                    "Joint Commission",
                    "OSHA"
                ],
                "regulatory_links": {
                    "HIPAA": "https://www.hhs.gov/hipaa/",
                    "CDC": "https://www.cdc.gov/infectioncontrol/",
                    "Joint Commission": "https://www.jointcommission.org/"
                },
                "requirements": {
                    "HIPAA": [
                        "Privacy procedures (164.502)",
                        "Security safeguards (164.306)",
                        "Breach notification (164.400)",
                        "Patient access rights (164.524)"
                    ],
                    "CDC": [
                        "Standard precautions",
                        "Transmission-based precautions",
                        "Hand hygiene",
                        "Personal protective equipment"
                    ]
                }
            },
            "technology": {
                "standards": [
                    "SOX",
                    "GDPR",
                    "ISO 27001",
                    "NIST"
                ],
                "regulatory_links": {
                    "SOX": "https://www.sec.gov/about/laws/soa2002.pdf",
                    "GDPR": "https://gdpr.eu/",
                    "ISO27001": "https://www.iso.org/isoiec-27001-information-security.html",
                    "NIST": "https://www.nist.gov/cyberframework"
                },
                "requirements": {
                    "SOX": [
                        "Internal controls (Section 404)",
                        "Financial reporting accuracy",
                        "Audit trail requirements",
                        "Change management"
                    ],
                    "GDPR": [
                        "Data protection by design (Article 25)",
                        "Consent management (Article 7)",
                        "Data breach notification (Article 33)",
                        "Data subject rights (Chapter 3)"
                    ]
                }
            }
        }
    
    def validate_compliance(self, template_data: Dict, industry: str, regulations: List[str]) -> ComplianceValidationResult:
        """Validate SOP template against regulatory requirements"""
        
        if industry not in self.compliance_data:
            raise HTTPException(status_code=400, detail=f"Unsupported industry: {industry}")
        
        industry_data = self.compliance_data[industry]
        missing_requirements = []
        recommendations = []
        regulatory_citations = []
        
        # Check each requested regulation
        for regulation in regulations:
            reg_key = regulation.upper().replace(" ", "_")
            
            if reg_key in industry_data.get("requirements", {}):
                requirements = industry_data["requirements"][reg_key]
                
                for requirement in requirements:
                    # Simple keyword-based compliance checking
                    if not self.check_requirement_in_template(requirement, template_data):
                        missing_requirements.append(f"{regulation}: {requirement}")
                    else:
                        # Add citation for met requirements
                        citation = RegulatoryRequirement(
                            regulation=regulation,
                            section=requirement.split("(")[-1].rstrip(")") if "(" in requirement else "General",
                            requirement=requirement.split("(")[0].strip(),
                            citation_url=industry_data.get("regulatory_links", {}).get(regulation.split()[0])
                        )
                        regulatory_citations.append(citation)
        
        # Generate recommendations
        if missing_requirements:
            recommendations.extend([
                "Consider adding missing regulatory requirements",
                "Review industry-specific compliance standards",
                "Consult with compliance experts for validation"
            ])
        
        # Calculate compliance score
        total_requirements = sum(len(reqs) for reqs in industry_data.get("requirements", {}).values())
        met_requirements = total_requirements - len(missing_requirements)
        compliance_score = (met_requirements / total_requirements * 100) if total_requirements > 0 else 100
        
        return ComplianceValidationResult(
            compliant=len(missing_requirements) == 0,
            missing_requirements=missing_requirements,
            recommendations=recommendations,
            regulatory_citations=regulatory_citations,
            compliance_score=round(compliance_score, 2)
        )
    
    def check_requirement_in_template(self, requirement: str, template_data: Dict) -> bool:
        """Check if a requirement is addressed in the template"""
        # Simple keyword matching (can be enhanced with NLP)
        requirement_lower = requirement.lower()
        template_text = str(template_data).lower()
        
        # Extract key terms from requirement
        key_terms = []
        if "hand washing" in requirement_lower or "hand hygiene" in requirement_lower:
            key_terms = ["hand", "wash", "hygiene"]
        elif "temperature" in requirement_lower:
            key_terms = ["temperature", "monitoring", "thermometer"]
        elif "allergen" in requirement_lower:
            key_terms = ["allergen", "allergy", "food safety"]
        elif "cleaning" in requirement_lower:
            key_terms = ["clean", "sanitiz", "disinfect"]
        elif "privacy" in requirement_lower:
            key_terms = ["privacy", "confidential", "protected"]
        elif "security" in requirement_lower:
            key_terms = ["security", "access", "password"]
        else:
            # Extract first few words as key terms
            key_terms = requirement_lower.split()[:3]
        
        # Check if any key terms are present
        return any(term in template_text for term in key_terms)

# Initialize service
compliance_service = ComplianceService()

@router.post("/compliance/validate", response_model=ComplianceValidationResult)
async def validate_compliance(request: ComplianceValidationRequest):
    """Validate SOP template against regulatory requirements"""
    
    return compliance_service.validate_compliance(
        request.template_data,
        request.industry,
        request.regulations
    )

@router.get("/compliance/standards", response_model=Dict[str, List[ComplianceStandard]])
async def get_compliance_standards(industry: Optional[str] = None):
    """Get available compliance standards"""
    
    standards = []
    compliance_data = compliance_service.compliance_data
    
    for ind, data in compliance_data.items():
        if industry and ind != industry:
            continue
        
        for standard in data.get("standards", []):
            standard_obj = ComplianceStandard(
                id=standard.lower().replace(" ", "_"),
                name=standard,
                description=f"{standard} compliance requirements for {ind}",
                industry=ind,
                requirements=data.get("requirements", {}).get(standard.upper().replace(" ", "_"), [])
            )
            standards.append(standard_obj)
    
    return {"standards": standards}

@router.get("/compliance/requirements/{industry}")
async def get_industry_requirements(industry: str):
    """Get compliance requirements for specific industry"""
    
    if industry not in compliance_service.compliance_data:
        raise HTTPException(status_code=404, detail=f"Industry '{industry}' not found")
    
    return compliance_service.compliance_data[industry]

@router.get("/compliance/check/{industry}/{regulation}")
async def check_regulation_support(industry: str, regulation: str):
    """Check if a specific regulation is supported for an industry"""
    
    if industry not in compliance_service.compliance_data:
        raise HTTPException(status_code=404, detail=f"Industry '{industry}' not found")
    
    industry_data = compliance_service.compliance_data[industry]
    reg_key = regulation.upper().replace(" ", "_")
    
    supported = reg_key in industry_data.get("requirements", {})
    
    return {
        "industry": industry,
        "regulation": regulation,
        "supported": supported,
        "requirements": industry_data.get("requirements", {}).get(reg_key, []) if supported else []
    }
