"""
Automation Pipeline Manager - Phase 2
Orchestrates the complete SOP generation, PDF creation, and deployment pipeline
Includes scheduling, monitoring, and error handling
"""

import os
import sys
import json
import logging
import asyncio
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'generators'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))

from sop_generator import SOPGenerator
from pdf_generator import EnhancedSOPPDFGenerator
from llm_client import FreeLLMClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory
os.makedirs('logs', exist_ok=True)


class AutomationPipelineManager:
    """
    Manages the complete automation pipeline for SOP generation
    """

    def __init__(self):
        """Initialize the pipeline manager"""
        self.template_types = ['restaurant', 'healthcare', 'it-onboarding', 'customer-service']
        self.output_base_dir = Path('outputs')
        self.monitoring_data = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'last_success': None,
            'errors': []
        }

        # Ensure output directories exist
        self.setup_directories()

        # Initialize components
        self.pdf_generator = EnhancedSOPPDFGenerator()

        logger.info("Automation Pipeline Manager initialized")

    def setup_directories(self):
        """Setup required directory structure"""
        directories = [
            'outputs/templates',
            'outputs/pdfs',
            'outputs/reports',
            'outputs/staging',
            'logs'
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        logger.info("Directory structure verified")

    def generate_single_template(self, template_type: str, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Generate a single SOP template

        Args:
            template_type: Type of template to generate
            force_regenerate: Force regeneration even if cached

        Returns:
            Dictionary with generation results
        """
        logger.info(f"Starting generation for {template_type}")
        start_time = datetime.now()

        try:
            # Initialize generator
            generator = SOPGenerator(template_type)

            # Clear cache if force regenerate
            if force_regenerate:
                logger.info(f"Force regenerating {template_type} - clearing cache")
                import shutil
                if generator.cache.cache_dir.exists():
                    shutil.rmtree(generator.cache.cache_dir)
                    generator.cache.cache_dir.mkdir(exist_ok=True)

            # Generate template
            template_content = generator.generate_template()

            # Save template
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            template_path = f"outputs/templates/{template_type}_{timestamp}.json"
            saved_path = generator.save_template(template_content, template_path)

            # Generate PDF
            pdf_path = f"outputs/pdfs/{template_type}_{timestamp}.pdf"
            pdf_output = self.pdf_generator.generate_enhanced_pdf(template_content, pdf_path)

            generation_time = (datetime.now() - start_time).total_seconds()

            result = {
                'template_type': template_type,
                'status': 'success',
                'template_path': saved_path,
                'pdf_path': pdf_output,
                'generation_time': generation_time,
                'timestamp': datetime.now().isoformat(),
                'stats': template_content.get('generation_stats', {}),
                'file_sizes': {
                    'template_json': os.path.getsize(saved_path),
                    'pdf': os.path.getsize(pdf_output)
                }
            }

            logger.info(f"Successfully generated {template_type} in {generation_time:.2f}s")
            return result

        except Exception as e:
            generation_time = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)

            logger.error(f"Failed to generate {template_type}: {error_msg}")

            result = {
                'template_type': template_type,
                'status': 'error',
                'error': error_msg,
                'generation_time': generation_time,
                'timestamp': datetime.now().isoformat()
            }

            return result

    def generate_all_templates(self, force_regenerate: bool = False, parallel: bool = True) -> Dict[str, Any]:
        """
        Generate all SOP templates

        Args:
            force_regenerate: Force regeneration even if cached
            parallel: Run generations in parallel

        Returns:
            Dictionary with all generation results
        """
        logger.info(f"Starting batch generation for all templates (parallel={parallel})")
        start_time = datetime.now()

        results = {
            'batch_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'start_time': start_time.isoformat(),
            'templates': {},
            'summary': {
                'total': len(self.template_types),
                'successful': 0,
                'failed': 0,
                'total_time': 0
            }
        }

        if parallel:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_template = {
                    executor.submit(self.generate_single_template, template_type, force_regenerate): template_type
                    for template_type in self.template_types
                }

                for future in as_completed(future_to_template):
                    template_type = future_to_template[future]
                    try:
                        result = future.result()
                        results['templates'][template_type] = result

                        if result['status'] == 'success':
                            results['summary']['successful'] += 1
                        else:
                            results['summary']['failed'] += 1

                    except Exception as e:
                        logger.error(f"Exception in parallel generation for {template_type}: {e}")
                        results['templates'][template_type] = {
                            'template_type': template_type,
                            'status': 'error',
                            'error': str(e),
                            'timestamp': datetime.now().isoformat()
                        }
                        results['summary']['failed'] += 1
        else:
            # Sequential execution
            for template_type in self.template_types:
                result = self.generate_single_template(template_type, force_regenerate)
                results['templates'][template_type] = result

                if result['status'] == 'success':
                    results['summary']['successful'] += 1
                else:
                    results['summary']['failed'] += 1

        # Calculate total time
        end_time = datetime.now()
        results['end_time'] = end_time.isoformat()
        results['summary']['total_time'] = (end_time - start_time).total_seconds()

        # Update monitoring data
        self.update_monitoring_data(results)

        # Generate report
        self.generate_batch_report(results)

        logger.info(f"Batch generation complete: {results['summary']['successful']}/{results['summary']['total']} successful")

        return results

    def update_monitoring_data(self, batch_results: Dict[str, Any]):
        """Update monitoring statistics"""
        self.monitoring_data['total_runs'] += 1
        self.monitoring_data['last_run'] = datetime.now().isoformat()

        if batch_results['summary']['failed'] == 0:
            self.monitoring_data['successful_runs'] += 1
            self.monitoring_data['last_success'] = datetime.now().isoformat()
        else:
            self.monitoring_data['failed_runs'] += 1

            # Collect errors
            for template_type, result in batch_results['templates'].items():
                if result['status'] == 'error':
                    self.monitoring_data['errors'].append({
                        'timestamp': result['timestamp'],
                        'template_type': template_type,
                        'error': result['error']
                    })

        # Keep only last 10 errors
        self.monitoring_data['errors'] = self.monitoring_data['errors'][-10:]

        # Save monitoring data
        monitoring_file = 'logs/monitoring.json'
        with open(monitoring_file, 'w') as f:
            json.dump(self.monitoring_data, f, indent=2)

    def generate_batch_report(self, batch_results: Dict[str, Any]):
        """Generate a comprehensive batch report"""
        report_path = f"outputs/reports/batch_report_{batch_results['batch_id']}.md"

        with open(report_path, 'w') as f:
            f.write(f"# SOP Generation Batch Report\n\n")
            f.write(f"**Batch ID**: {batch_results['batch_id']}\n")
            f.write(f"**Generated**: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
            f.write(f"**Total Time**: {batch_results['summary']['total_time']:.2f} seconds\n\n")

            f.write(f"## Summary\n\n")
            f.write(f"- **Total Templates**: {batch_results['summary']['total']}\n")
            f.write(f"- **Successful**: {batch_results['summary']['successful']}\n")
            f.write(f"- **Failed**: {batch_results['summary']['failed']}\n")
            f.write(f"- **Success Rate**: {(batch_results['summary']['successful']/batch_results['summary']['total']*100):.1f}%\n\n")

            f.write(f"## Template Details\n\n")

            for template_type, result in batch_results['templates'].items():
                status_icon = "✅" if result['status'] == 'success' else "❌"
                f.write(f"### {status_icon} {template_type.title()}\n\n")

                if result['status'] == 'success':
                    stats = result.get('stats', {})
                    f.write(f"- **Status**: Success\n")
                    f.write(f"- **Generation Time**: {result['generation_time']:.2f}s\n")
                    f.write(f"- **Sections Generated**: {stats.get('successful_sections', 0)}/{stats.get('total_sections', 0)}\n")
                    f.write(f"- **From Cache**: {stats.get('cached_sections', 0)}\n")
                    f.write(f"- **Template File**: {result['template_path']}\n")
                    f.write(f"- **PDF File**: {result['pdf_path']}\n")
                    f.write(f"- **File Sizes**: JSON: {result['file_sizes']['template_json']:,} bytes, PDF: {result['file_sizes']['pdf']:,} bytes\n\n")
                else:
                    f.write(f"- **Status**: Failed\n")
                    f.write(f"- **Error**: {result['error']}\n")
                    f.write(f"- **Generation Time**: {result['generation_time']:.2f}s\n\n")

        logger.info(f"Batch report generated: {report_path}")

    def send_notification(self, subject: str, message: str, is_error: bool = False):
        """
        Send notification email or webhook

        Args:
            subject: Email subject
            message: Message content
            is_error: Whether this is an error notification
        """
        try:
            # Email notification
            smtp_server = os.getenv('SMTP_SERVER')
            smtp_port = int(os.getenv('SMTP_PORT', 587))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            notification_email = os.getenv('NOTIFICATION_EMAIL')

            if all([smtp_server, smtp_username, smtp_password, notification_email]):
                msg = MIMEMultipart()
                msg['From'] = smtp_username
                msg['To'] = notification_email
                msg['Subject'] = f"SOP Pipeline: {subject}"

                body = f"""
SOP Generation Pipeline Notification

{message}

Timestamp: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
Pipeline Status: {'ERROR' if is_error else 'SUCCESS'}

---
Automated SOP Generation System
                """

                msg.attach(MIMEText(body, 'plain'))

                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
                text = msg.as_string()
                server.sendmail(smtp_username, notification_email, text)
                server.quit()

                logger.info("Email notification sent successfully")

            # Slack webhook notification
            slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
            if slack_webhook:
                import requests

                color = "danger" if is_error else "good"
                slack_message = {
                    "text": f"SOP Pipeline: {subject}",
                    "attachments": [{
                        "color": color,
                        "fields": [{
                            "title": "Message",
                            "value": message,
                            "short": False
                        }],
                        "footer": "SOP Generation Pipeline",
                        "ts": int(datetime.now().timestamp())
                    }]
                }

                response = requests.post(slack_webhook, json=slack_message)
                if response.status_code == 200:
                    logger.info("Slack notification sent successfully")
                else:
                    logger.warning(f"Failed to send Slack notification: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def run_scheduled_generation(self):
        """Run scheduled generation with error handling and notifications"""
        logger.info("Starting scheduled generation run")

        try:
            # Run batch generation
            results = self.generate_all_templates(force_regenerate=False, parallel=True)

            # Check results and send notifications
            summary = results['summary']
            if summary['failed'] == 0:
                # Success notification
                message = f"""
Batch generation completed successfully!

✅ All {summary['total']} templates generated successfully
⏱️ Total time: {summary['total_time']:.2f} seconds
📊 Success rate: 100%

Generated templates:
{', '.join(results['templates'].keys())}
                """
                self.send_notification("Batch Generation Successful", message, is_error=False)
            else:
                # Partial failure notification
                failed_templates = [name for name, result in results['templates'].items() if result['status'] == 'error']
                message = f"""
Batch generation completed with errors!

✅ Successful: {summary['successful']}/{summary['total']}
❌ Failed: {summary['failed']}/{summary['total']}
⏱️ Total time: {summary['total_time']:.2f} seconds
📊 Success rate: {(summary['successful']/summary['total']*100):.1f}%

Failed templates: {', '.join(failed_templates)}

Please check the logs for detailed error information.
                """
                self.send_notification("Batch Generation Partial Failure", message, is_error=True)

        except Exception as e:
            # Complete failure notification
            error_message = f"""
Batch generation failed completely!

❌ Error: {str(e)}
⏱️ Timestamp: {datetime.now().isoformat()}

Please check the logs and system status immediately.
            """
            self.send_notification("Batch Generation Failed", error_message, is_error=True)
            logger.error(f"Scheduled generation failed: {e}")

    def setup_scheduler(self):
        """Setup the generation scheduler"""
        # Daily generation at 2 AM
        schedule.every().day.at("02:00").do(self.run_scheduled_generation)

        # Weekly full regeneration on Sundays at 1 AM
        schedule.every().sunday.at("01:00").do(
            lambda: self.generate_all_templates(force_regenerate=True, parallel=True)
        )

        # Health check every 6 hours
        schedule.every(6).hours.do(self.health_check)

        logger.info("Scheduler configured:")
        logger.info("- Daily generation: 2:00 AM")
        logger.info("- Weekly full regeneration: Sunday 1:00 AM")
        logger.info("- Health check: Every 6 hours")

    def health_check(self):
        """Perform system health check"""
        logger.info("Performing health check")

        health_status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {}
        }

        try:
            # Check disk space
            import shutil
            total, used, free = shutil.disk_usage('.')
            free_gb = free // (1024**3)
            health_status['checks']['disk_space'] = {
                'free_gb': free_gb,
                'status': 'ok' if free_gb > 1 else 'warning'
            }

            # Check output directories
            required_dirs = ['outputs/templates', 'outputs/pdfs', 'logs']
            for directory in required_dirs:
                exists = os.path.exists(directory)
                health_status['checks'][f'directory_{directory.replace("/", "_")}'] = {
                    'exists': exists,
                    'status': 'ok' if exists else 'error'
                }

            # Check LLM client
            try:
                llm_client = FreeLLMClient()
                available_providers = llm_client.get_available_providers()
                health_status['checks']['llm_providers'] = {
                    'available': available_providers,
                    'count': len(available_providers),
                    'status': 'ok' if available_providers else 'warning'
                }
            except Exception as e:
                health_status['checks']['llm_providers'] = {
                    'error': str(e),
                    'status': 'error'
                }

            # Check recent generation success
            if self.monitoring_data['last_success']:
                last_success = datetime.fromisoformat(self.monitoring_data['last_success'])
                hours_since_success = (datetime.now() - last_success).total_seconds() / 3600
                health_status['checks']['recent_success'] = {
                    'hours_since_last_success': hours_since_success,
                    'status': 'ok' if hours_since_success < 48 else 'warning'
                }

            # Determine overall status
            error_checks = [check for check in health_status['checks'].values() if check.get('status') == 'error']
            warning_checks = [check for check in health_status['checks'].values() if check.get('status') == 'warning']

            if error_checks:
                health_status['status'] = 'error'
            elif warning_checks:
                health_status['status'] = 'warning'

            # Save health status
            health_file = 'logs/health_status.json'
            with open(health_file, 'w') as f:
                json.dump(health_status, f, indent=2)

            # Send notification if unhealthy
            if health_status['status'] != 'healthy':
                issues = []
                for check_name, check_data in health_status['checks'].items():
                    if check_data.get('status') in ['error', 'warning']:
                        issues.append(f"- {check_name}: {check_data.get('status', 'unknown')}")

                message = f"""
Health check detected issues:

{chr(10).join(issues)}

Please investigate and resolve these issues.
                """
                self.send_notification(f"Health Check: {health_status['status'].title()}", message, is_error=True)

            logger.info(f"Health check completed: {health_status['status']}")

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.send_notification("Health Check Failed", f"Health check encountered an error: {str(e)}", is_error=True)

    def run_scheduler(self):
        """Run the scheduler loop"""
        self.setup_scheduler()

        logger.info("Starting scheduler loop. Press Ctrl+C to stop.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            self.send_notification("Scheduler Error", f"Scheduler encountered an error: {str(e)}", is_error=True)


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description='SOP Generation Automation Pipeline Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single template generation
  python pipeline_manager.py --generate restaurant

  # Run all templates
  python pipeline_manager.py --generate-all

  # Force regeneration (clear cache)
  python pipeline_manager.py --generate-all --force

  # Start scheduler
  python pipeline_manager.py --scheduler

  # Run health check
  python pipeline_manager.py --health-check
        """
    )

    parser.add_argument('--generate', help='Generate single template type')
    parser.add_argument('--generate-all', action='store_true', help='Generate all templates')
    parser.add_argument('--force', action='store_true', help='Force regeneration (clear cache)')
    parser.add_argument('--parallel', action='store_true', default=True, help='Run in parallel (default: True)')
    parser.add_argument('--scheduler', action='store_true', help='Start the scheduler')
    parser.add_argument('--health-check', action='store_true', help='Run health check')

    args = parser.parse_args()

    # Initialize pipeline manager
    pipeline = AutomationPipelineManager()

    try:
        if args.generate:
            # Generate single template
            result = pipeline.generate_single_template(args.generate, args.force)
            print(f"\n🎯 Generation Result for {args.generate}:")
            print(f"Status: {result['status']}")
            if result['status'] == 'success':
                print(f"Template: {result['template_path']}")
                print(f"PDF: {result['pdf_path']}")
                print(f"Time: {result['generation_time']:.2f}s")
            else:
                print(f"Error: {result['error']}")

        elif args.generate_all:
            # Generate all templates
            results = pipeline.generate_all_templates(args.force, args.parallel)
            print(f"\n🎯 Batch Generation Results:")
            print(f"Successful: {results['summary']['successful']}/{results['summary']['total']}")
            print(f"Total time: {results['summary']['total_time']:.2f}s")

        elif args.health_check:
            # Run health check
            pipeline.health_check()
            print("✅ Health check completed. Check logs/health_status.json for details.")

        elif args.scheduler:
            # Start scheduler
            pipeline.run_scheduler()

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
