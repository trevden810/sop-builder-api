"""
Daily automation script for SOP template updates
Checks for compliance changes, generates updates, and prepares for deployment
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
import schedule
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.sop_generator import SOPGenerator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyUpdateManager:
    """Manages daily updates for SOP templates"""
    
    def __init__(self):
        self.compliance_sources = {
            'FDA': {
                'url': 'https://www.fda.gov/food/guidance-regulation-food-and-dietary-supplements',
                'selector': '.guidance-recent',
                'template_types': ['restaurant']
            },
            'HIPAA': {
                'url': 'https://www.hhs.gov/hipaa/for-professionals/index.html',
                'selector': '.recent-updates',
                'template_types': ['healthcare']
            },
            'NIST': {
                'url': 'https://www.nist.gov/cyberframework',
                'selector': '.news-updates',
                'template_types': ['it-onboarding']
            }
        }
        
        # Initialize Google Sheets client
        self.sheets_client = self._init_google_sheets()
        
    def _init_google_sheets(self):
        """Initialize Google Sheets API client"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH'),
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return gspread.authorize(credentials)
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {str(e)}")
            return None
    
    def check_compliance_updates(self) -> List[Dict]:
        """Check for regulatory updates from various sources"""
        updates = []
        
        for agency, config in self.compliance_sources.items():
            logger.info(f"Checking {agency} for updates...")
            
            try:
                response = requests.get(config['url'], timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for recent updates
                recent_items = soup.select(config['selector'])[:5]  # Get last 5 items
                
                for item in recent_items:
                    # Extract date if available
                    date_elem = item.find(class_=['date', 'published', 'timestamp'])
                    if date_elem:
                        update_date = date_elem.text.strip()
                        # Check if update is within last 7 days
                        # (Simple check - in production, parse dates properly)
                        updates.append({
                            'agency': agency,
                            'title': item.text.strip()[:100],
                            'url': config['url'],
                            'affected_templates': config['template_types'],
                            'date': update_date
                        })
                
            except Exception as e:
                logger.error(f"Error checking {agency}: {str(e)}")
        
        return updates
    
    def update_compliance_spreadsheet(self, updates: List[Dict]):
        """Update Google Sheets with compliance changes"""
        if not self.sheets_client:
            logger.warning("Google Sheets client not initialized")
            return
        
        try:
            sheet = self.sheets_client.open_by_key(
                os.getenv('COMPLIANCE_SHEET_ID')
            ).worksheet('Compliance_Updates')
            
            # Add new updates
            for update in updates:
                row = [
                    update['agency'],
                    update['title'],
                    update['date'],
                    datetime.now().isoformat(),
                    ', '.join(update['affected_templates']),
                    'Pending Review'
                ]
                sheet.append_row(row)
            
            logger.info(f"Added {len(updates)} updates to compliance sheet")
            
        except Exception as e:
            logger.error(f"Error updating spreadsheet: {str(e)}")
    
    def generate_update_content(self, template_type: str, updates: List[Dict]) -> Dict:
        """Generate updated content for templates based on compliance changes"""
        logger.info(f"Generating updates for {template_type}")
        
        # Filter updates relevant to this template
        relevant_updates = [u for u in updates if template_type in u.get('affected_templates', [])]
        
        if not relevant_updates:
            logger.info(f"No updates needed for {template_type}")
            return None
        
        # Generate update summary
        update_summary = {
            'template_type': template_type,
            'update_date': datetime.now().isoformat(),
            'changes': []
        }
        
        for update in relevant_updates:
            # Use AI to generate specific changes needed
            generator = SOPGenerator(template_type)
            
            # Generate section updates
            change_prompt = f"""
            Based on this regulatory update:
            {update['title']}
            
            What specific changes need to be made to the {template_type} SOP template?
            List specific sections that need updates and what changes are required.
            """
            
            # In production, call AI API here
            # For now, create placeholder
            update_summary['changes'].append({
                'agency': update['agency'],
                'description': update['title'],
                'sections_affected': ['Compliance Requirements', 'Documentation'],
                'priority': 'High'
            })
        
        return update_summary
    
    def prepare_staging_updates(self, updates: Dict):
        """Prepare updates in staging area for review"""
        staging_dir = 'outputs/staging'
        os.makedirs(staging_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        staging_file = os.path.join(staging_dir, f"updates_{timestamp}.json")
        
        with open(staging_file, 'w') as f:
            json.dump(updates, f, indent=2)
        
        logger.info(f"Staging updates saved to {staging_file}")
        
        # Create summary report
        self.create_summary_report(updates)
    
    def create_summary_report(self, all_updates: Dict):
        """Create human-readable summary of updates"""
        report_path = f"outputs/reports/daily_update_{datetime.now().strftime('%Y%m%d')}.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write("# Daily SOP Template Update Report\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%B %d, %Y')}\n\n")
            
            if not all_updates:
                f.write("No updates required today.\n")
            else:
                f.write("## Updates Required\n\n")
                
                for template_type, updates in all_updates.items():
                    f.write(f"### {template_type.title()} Template\n\n")
                    
                    for change in updates.get('changes', []):
                        f.write(f"- **{change['agency']}**: {change['description']}\n")
                        f.write(f"  - Priority: {change['priority']}\n")
                        f.write(f"  - Sections: {', '.join(change['sections_affected'])}\n\n")
        
        logger.info(f"Summary report created: {report_path}")
    
    def send_notifications(self, updates: Dict):
        """Send notifications about updates"""
        if not updates:
            return
        
        # Slack notification
        slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        if slack_webhook:
            message = {
                "text": f"📋 SOP Template Updates Available",
                "attachments": [{
                    "color": "warning",
                    "fields": [
                        {
                            "title": "Templates Requiring Updates",
                            "value": ', '.join(updates.keys()),
                            "short": False
                        }
                    ]
                }]
            }
            
            try:
                requests.post(slack_webhook, json=message)
                logger.info("Slack notification sent")
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {str(e)}")
    
    def run_daily_update(self):
        """Main function to run daily updates"""
        logger.info("Starting daily update process...")
        
        # Check for compliance updates
        compliance_updates = self.check_compliance_updates()
        
        # Update tracking spreadsheet
        if compliance_updates:
            self.update_compliance_spreadsheet(compliance_updates)
        
        # Generate updates for each template type
        all_updates = {}
        template_types = ['restaurant', 'healthcare', 'it-onboarding', 'customer-service']
        
        for template_type in template_types:
            updates = self.generate_update_content(template_type, compliance_updates)
            if updates:
                all_updates[template_type] = updates
        
        # Prepare staging area
        if all_updates:
            self.prepare_staging_updates(all_updates)
            self.send_notifications(all_updates)
        
        logger.info("Daily update process complete")
        
        return all_updates


def main():
    """Main execution function"""
    manager = DailyUpdateManager()
    
    # Run once immediately
    manager.run_daily_update()
    
    # Schedule for daily execution
    schedule.every().day.at("09:00").do(manager.run_daily_update)
    
    logger.info("Daily update scheduler started. Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()
