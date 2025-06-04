"""
Simple HTTP server for SOP Builder MVP API
Using built-in Python modules to avoid dependency conflicts
"""

import json
import os
import sys
import threading
import uuid
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import asyncio

# Add scripts directory to path
project_root = Path(__file__).parent.parent
scripts_path = project_root / "scripts"
sys.path.append(str(scripts_path))

# Import existing generators
try:
    from generators.sop_generator import SOPGenerator
    from utils.llm_client import FreeLLMClient
    GENERATORS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import generators: {e}")
    GENERATORS_AVAILABLE = False

# In-memory storage for generation jobs
generation_jobs = {}

class SOPAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for SOP Builder API"""
    
    def _set_cors_headers(self):
        """Set CORS headers for cross-origin requests"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
    
    def _send_json_response(self, data, status_code=200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        
        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_error_response(self, message, status_code=400):
        """Send error response"""
        error_data = {
            "error": {
                "message": message,
                "status_code": status_code
            }
        }
        self._send_json_response(error_data, status_code)
    
    def do_OPTIONS(self):
        """Handle preflight OPTIONS requests"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        try:
            if path == '/':
                self._send_json_response({
                    "message": "SOP Builder MVP API is running!",
                    "version": "1.0.0"
                })
            
            elif path == '/api/health':
                self._send_json_response({
                    "status": "healthy",
                    "version": "1.0.0",
                    "generators_available": GENERATORS_AVAILABLE,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif path == '/api/v1/templates':
                self._handle_get_templates(query_params)
            
            elif path.startswith('/api/v1/templates/'):
                template_id = path.split('/')[-1]
                self._handle_get_template_by_id(template_id)
            
            elif path == '/api/v1/industries':
                self._handle_get_industries()
            
            elif path.startswith('/api/v1/generate/') and path.endswith('/status'):
                generation_id = path.split('/')[-2]
                self._handle_get_generation_status(generation_id)
            
            else:
                self._send_error_response("Endpoint not found", 404)
        
        except Exception as e:
            self._send_error_response(f"Internal server error: {str(e)}", 500)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            request_body = self.rfile.read(content_length).decode('utf-8')
            request_data = json.loads(request_body) if request_body else {}
            
            if path == '/api/v1/generate':
                self._handle_start_generation(request_data)
            
            elif path == '/api/v1/documents/preview':
                self._handle_generate_preview(request_data)
            
            else:
                self._send_error_response("Endpoint not found", 404)
        
        except json.JSONDecodeError:
            self._send_error_response("Invalid JSON in request body", 400)
        except Exception as e:
            self._send_error_response(f"Internal server error: {str(e)}", 500)
    
    def _handle_get_templates(self, query_params):
        """Handle GET /api/v1/templates"""
        industry_filter = query_params.get('industry', [None])[0]
        
        templates = [
            {
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
                    {"id": "cleaning-procedures", "label": "Include Cleaning Procedures", "default": True}
                ]
            },
            {
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
                    {"id": "cleaning-schedule", "label": "Include Deep Cleaning Schedule", "default": True}
                ]
            },
            {
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
                    {"id": "consent-forms", "label": "Include Consent Form Procedures", "default": True}
                ]
            }
        ]
        
        # Filter by industry if specified
        if industry_filter:
            templates = [t for t in templates if t["industry"] == industry_filter]
        
        self._send_json_response({"templates": templates})
    
    def _handle_get_template_by_id(self, template_id):
        """Handle GET /api/v1/templates/{template_id}"""
        template_details = {
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
                    {"id": "haccp", "label": "Include HACCP Procedures", "default": True}
                ],
                "content_sections": ["introduction", "procedures", "safety", "compliance"],
                "regulatory_requirements": {
                    "fda_food_code": "2022 FDA Food Code Section 2-301.11",
                    "haccp": "HACCP Principle 1-7 Implementation"
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
                    {"id": "consent-forms", "label": "Include Consent Form Procedures", "default": True}
                ],
                "content_sections": ["introduction", "intake_procedures", "documentation", "compliance"],
                "regulatory_requirements": {
                    "hipaa": "HIPAA Privacy Rule 45 CFR 164.502",
                    "joint_commission": "Joint Commission Patient Safety Standards",
                    "cms": "CMS Conditions of Participation"
                }
            }
        }
        
        if template_id in template_details:
            self._send_json_response(template_details[template_id])
        else:
            self._send_error_response("Template not found", 404)
    
    def _handle_get_industries(self):
        """Handle GET /api/v1/industries"""
        industries = [
            {
                "id": "restaurant",
                "name": "Restaurant & Food Service",
                "template_count": 2,
                "compliance_standards": ["FDA Food Code", "HACCP", "ServSafe", "OSHA"]
            }
        ]
        self._send_json_response({"industries": industries})
    
    def _handle_start_generation(self, request_data):
        """Handle POST /api/v1/generate"""
        # Validate request
        if not request_data.get('template_id'):
            self._send_error_response("template_id is required", 400)
            return
        
        if not request_data.get('company_info', {}).get('name'):
            self._send_error_response("company_info.name is required", 400)
            return
        
        # Generate unique ID
        generation_id = str(uuid.uuid4())
        
        # Create job status
        generation_jobs[generation_id] = {
            "generation_id": generation_id,
            "status": "pending",
            "progress": 0,
            "current_step": "Queued for generation...",
            "request_data": request_data,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Start background generation if generators are available
        if GENERATORS_AVAILABLE:
            threading.Thread(
                target=self._background_generation,
                args=(generation_id, request_data),
                daemon=True
            ).start()
        else:
            # Mock generation for testing
            threading.Thread(
                target=self._mock_generation,
                args=(generation_id,),
                daemon=True
            ).start()
        
        self._send_json_response({
            "generation_id": generation_id,
            "status": "pending",
            "estimated_completion": datetime.utcnow().isoformat(),
            "websocket_url": f"/ws/generation/{generation_id}"
        }, 202)
    
    def _handle_get_generation_status(self, generation_id):
        """Handle GET /api/v1/generate/{generation_id}/status"""
        if generation_id in generation_jobs:
            self._send_json_response(generation_jobs[generation_id])
        else:
            self._send_error_response("Generation job not found", 404)
    
    def _handle_generate_preview(self, request_data):
        """Handle POST /api/v1/documents/preview"""
        # Mock preview for now
        import base64
        mock_pdf = b"Mock PDF content for preview"
        preview_base64 = base64.b64encode(mock_pdf).decode('utf-8')
        
        self._send_json_response({
            "preview_base64": preview_base64,
            "content_type": "application/pdf"
        })
    
    def _background_generation(self, generation_id, request_data):
        """Background SOP generation using existing generators"""
        try:
            job = generation_jobs[generation_id]
            
            # Update status
            job["status"] = "processing"
            job["progress"] = 10
            job["current_step"] = "Initializing generation..."
            
            # Initialize generator
            template_type = "restaurant"  # Map from template_id
            generator = SOPGenerator(template_type)
            
            job["progress"] = 30
            job["current_step"] = "Generating content with AI..."
            
            # Generate SOP
            template_content = generator.generate_template()
            
            job["progress"] = 90
            job["current_step"] = "Finalizing document..."
            
            # Complete
            job["status"] = "completed"
            job["progress"] = 100
            job["current_step"] = "Generation complete!"
            job["result"] = {
                "template_data": template_content,
                "generation_metadata": {
                    "template_id": request_data["template_id"],
                    "company_name": request_data["company_info"]["name"],
                    "generated_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            job["current_step"] = f"Generation failed: {str(e)}"
    
    def _mock_generation(self, generation_id):
        """Mock generation for testing when generators not available"""
        import time
        
        job = generation_jobs[generation_id]
        
        steps = [
            (20, "Initializing AI provider..."),
            (40, "Generating introduction section..."),
            (60, "Creating procedure steps..."),
            (80, "Adding compliance requirements..."),
            (100, "Generation complete!")
        ]
        
        job["status"] = "processing"
        
        for progress, step in steps:
            time.sleep(2)  # Simulate work
            job["progress"] = progress
            job["current_step"] = step
        
        job["status"] = "completed"
        job["result"] = {
            "template_data": {"mock": "data"},
            "generation_metadata": {
                "template_id": job["request_data"]["template_id"],
                "company_name": job["request_data"]["company_info"]["name"],
                "generated_at": datetime.utcnow().isoformat()
            }
        }

def run_server(port=8000):
    """Run the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, SOPAPIHandler)
    
    print(f"🚀 SOP Builder MVP API Server starting on port {port}")
    print(f"📋 Health check: http://localhost:{port}/api/health")
    print(f"📚 Templates: http://localhost:{port}/api/v1/templates")
    print(f"🔧 Generators available: {GENERATORS_AVAILABLE}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.shutdown()

if __name__ == "__main__":
    run_server()
