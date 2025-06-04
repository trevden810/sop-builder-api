"""
Deployment script for SOP templates
Handles uploading to Gumroad and sending customer notifications
"""

import os
import json
import requests
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentManager:
    """Manage deployment of SOP templates to distribution platforms"""
    
    def __init__(self):
        self.gumroad_token = os.getenv('GUMROAD_ACCESS_TOKEN')
        self.product_ids = json.loads(os.getenv('GUMROAD_PRODUCT_IDS', '{}'))
        self.mailchimp_api_key = os.getenv('MAILCHIMP_API_KEY')
        self.mailchimp_list_id = os.getenv('MAILCHIMP_LIST_ID')
        
    def upload_to_gumroad(self, template_type, pdf_path, version="1.0"):
        """Upload PDF to Gumroad product"""
        if template_type not in self.product_ids:
            logger.error(f"No Gumroad product ID found for {template_type}")
            return False
        
        product_id = self.product_ids[template_type]
        
        # Prepare the file
        with open(pdf_path, 'rb') as f:
            files = {
                'file': (os.path.basename(pdf_path), f, 'application/pdf')
            }
            
            # Update product with new file
            url = f"https://api.gumroad.com/v2/products/{product_id}"
            
            data = {
                'access_token': self.gumroad_token,
                'name': f"{template_type.title()} SOP Template v{version}",
                'description': self.get_product_description(template_type),
                'tags[]': ['sop', 'template', 'compliance', template_type]
            }
            
            try:
                response = requests.put(url, data=data, files=files)
                response.raise_for_status()
                
                logger.info(f"Successfully uploaded {template_type} to Gumroad")
                return True
                
            except Exception as e:
                logger.error(f"Failed to upload to Gumroad: {str(e)}")
                return False
    
    def get_product_description(self, template_type):
        """Get product description for Gumroad"""
        descriptions = {
            'restaurant': """
            🍽️ Restaurant Food Safety SOP Template - 2025 Edition
            
            ✅ FDA Food Code 2022 Compliant
            ✅ HACCP Principles Built-In
            ✅ Health Department Ready
            ✅ Crisis Response Protocols
            ✅ Employee Training Materials
            ✅ Temperature Logs & Checklists
            ✅ QR Codes for Quick Access to Regulations
            
            💡 Perfect for restaurants, cafes, food trucks, and catering businesses
            📄 45+ pages of comprehensive procedures
            🔄 Free updates for 12 months
            📧 Email support included
            
            ⚡ Instant download after purchase
            """,
            'healthcare': """
            🏥 Healthcare HIPAA Compliance SOP Template - 2025 Edition
            
            ✅ 2025 HIPAA Updates Included
            ✅ Privacy & Security Rule Procedures
            ✅ Breach Notification Workflows
            ✅ Risk Assessment Templates
            ✅ Employee Training Documentation
            ✅ Vendor Management Forms
            ✅ Audit Preparation Guides
            
            💡 Essential for medical practices, clinics, and healthcare providers
            📄 60+ pages of detailed procedures
            🔄 Quarterly compliance updates
            📧 Priority support included
            
            ⚡ Instant download after purchase
            """
        }
        
        return descriptions.get(template_type, "Premium SOP Template with comprehensive compliance procedures.")
    
    def create_update_email(self, template_type, changes):
        """Create update notification email"""
        subject = f"Important Update: Your {template_type.title()} SOP Template"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2C3E50;">Important Compliance Update</h2>
                
                <p>Hello!</p>
                
                <p>We've updated your <strong>{template_type.title()} SOP Template</strong> to reflect the latest regulatory changes.</p>
                
                <h3 style="color: #3498DB;">What's Changed:</h3>
                <ul>
        """
        
        for change in changes:
            html_content += f"""
                <li>
                    <strong>{change['agency']}</strong>: {change['description']}<br>
                    <em>Sections affected: {', '.join(change['sections_affected'])}</em>
                </li>
            """
        
        html_content += """
                </ul>
                
                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #E74C3C; margin-top: 0;">Action Required</h3>
                    <p>Please download the updated template from your Gumroad library to ensure compliance with the latest regulations.</p>
                    <a href="https://gumroad.com/library" style="display: inline-block; background-color: #3498DB; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Access Your Updated Template</a>
                </div>
                
                <p>If you have any questions about these updates, please don't hesitate to reach out.</p>
                
                <p>Best regards,<br>
                The Premium SOP Templates Team</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #666;">
                    You're receiving this email because you purchased our {template_type.title()} SOP Template. 
                    These updates are part of your included 12-month update service.
                </p>
            </div>
        </body>
        </html>
        """
        
        return subject, html_content
    
    def send_update_notifications(self, template_type, changes, test_mode=False):
        """Send update notifications via Mailchimp"""
        if not self.mailchimp_api_key:
            logger.warning("Mailchimp API key not configured")
            return
        
        subject, html_content = self.create_update_email(template_type, changes)
        
        # Mailchimp campaign creation
        headers = {
            'Authorization': f'Bearer {self.mailchimp_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Create campaign
        campaign_data = {
            "type": "regular",
            "recipients": {
                "list_id": self.mailchimp_list_id,
                "segment_opts": {
                    "conditions": [{
                        "field": "PRODUCT",
                        "op": "contains",
                        "value": template_type
                    }]
                }
            },
            "settings": {
                "subject_line": subject,
                "from_name": "Premium SOP Templates",
                "reply_to": os.getenv('ERROR_EMAIL', 'support@example.com')
            }
        }
        
        if test_mode:
            logger.info("Test mode: Would send email with subject: " + subject)
            return True
        
        try:
            # Create campaign
            response = requests.post(
                f"https://{self._get_mailchimp_datacenter()}.api.mailchimp.com/3.0/campaigns",
                headers=headers,
                json=campaign_data
            )
            response.raise_for_status()
            
            campaign_id = response.json()['id']
            
            # Set campaign content
            content_response = requests.put(
                f"https://{self._get_mailchimp_datacenter()}.api.mailchimp.com/3.0/campaigns/{campaign_id}/content",
                headers=headers,
                json={"html": html_content}
            )
            content_response.raise_for_status()
            
            # Send campaign
            send_response = requests.post(
                f"https://{self._get_mailchimp_datacenter()}.api.mailchimp.com/3.0/campaigns/{campaign_id}/actions/send",
                headers=headers
            )
            send_response.raise_for_status()
            
            logger.info(f"Successfully sent update notifications for {template_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notifications: {str(e)}")
            return False
    
    def _get_mailchimp_datacenter(self):
        """Extract datacenter from API key"""
        return self.mailchimp_api_key.split('-')[-1]
    
    def deploy_template(self, template_type, pdf_path, changes=None):
        """Full deployment process"""
        logger.info(f"Starting deployment for {template_type}")
        
        # Upload to Gumroad
        if self.upload_to_gumroad(template_type, pdf_path):
            logger.info("Gumroad upload successful")
        else:
            logger.error("Gumroad upload failed")
            return False
        
        # Send notifications if there are changes
        if changes:
            self.send_update_notifications(template_type, changes['changes'])
        
        # Log deployment
        self.log_deployment(template_type, pdf_path)
        
        return True
    
    def log_deployment(self, template_type, pdf_path):
        """Log deployment details"""
        log_entry = {
            'template_type': template_type,
            'pdf_path': pdf_path,
            'timestamp': datetime.now().isoformat(),
            'version': self._extract_version_from_path(pdf_path)
        }
        
        log_file = 'deployments.log'
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def _extract_version_from_path(self, pdf_path):
        """Extract version number from file path"""
        # Simple extraction - in production, use proper versioning
        import re
        match = re.search(r'v(\d+\.\d+)', pdf_path)
        return match.group(1) if match else "1.0"


def main():
    """Deploy templates based on staging updates"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy SOP templates')
    parser.add_argument('--staging-file', help='Staging updates JSON file')
    parser.add_argument('--template-type', help='Specific template to deploy')
    parser.add_argument('--pdf-path', help='Path to PDF file')
    parser.add_argument('--test', action='store_true', help='Test mode (no actual deployment)')
    
    args = parser.parse_args()
    
    manager = DeploymentManager()
    
    if args.staging_file:
        # Deploy from staging file
        with open(args.staging_file, 'r') as f:
            updates = json.load(f)
        
        for template_type, template_updates in updates.items():
            # Generate PDF path (assuming it exists)
            pdf_path = f"outputs/pdfs/{template_type}_latest.pdf"
            
            if os.path.exists(pdf_path):
                if args.test:
                    logger.info(f"TEST MODE: Would deploy {template_type}")
                else:
                    manager.deploy_template(template_type, pdf_path, template_updates)
            else:
                logger.warning(f"PDF not found for {template_type}: {pdf_path}")
    
    elif args.template_type and args.pdf_path:
        # Deploy specific template
        if args.test:
            logger.info(f"TEST MODE: Would deploy {args.template_type}")
        else:
            manager.deploy_template(args.template_type, args.pdf_path)
    
    else:
        print("Please specify either --staging-file or both --template-type and --pdf-path")


if __name__ == "__main__":
    main()
