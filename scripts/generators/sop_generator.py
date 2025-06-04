"""
SOP Template Generator - Enhanced automation script with error handling, caching, and progress tracking
Generates SOP templates using AI and assembles them into final products
"""

import os
import json
import logging
import time
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
import yaml
from tqdm import tqdm
from pathlib import Path
import sys

# Add utils to path for LLM client import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from llm_client import FreeLLMClient, LLMProvider

# Load environment variables - try multiple locations
load_dotenv()  # Load from current directory
load_dotenv('.env')  # Load from current directory explicitly
load_dotenv('../../.env')  # Load from parent directory

# Configure enhanced logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG', 'False').lower() == 'true' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sop_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise e

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


class TemplateCache:
    """Simple file-based cache for generated content"""

    def __init__(self, cache_dir: str = "cache", cache_duration_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_duration = timedelta(hours=cache_duration_hours)
        logger.info(f"Template cache initialized at {self.cache_dir}")

    def _get_cache_key(self, template_type: str, section_name: str, prompt_hash: str) -> str:
        """Generate a unique cache key for the content"""
        key_data = f"{template_type}_{section_name}_{prompt_hash}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key"""
        return self.cache_dir / f"{cache_key}.pkl"

    def get(self, template_type: str, section_name: str, prompt: str) -> Optional[str]:
        """Retrieve cached content if available and not expired"""
        try:
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            cache_key = self._get_cache_key(template_type, section_name, prompt_hash)
            cache_path = self._get_cache_path(cache_key)

            if not cache_path.exists():
                return None

            # Check if cache is expired
            cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if datetime.now() - cache_time > self.cache_duration:
                logger.debug(f"Cache expired for {section_name}")
                cache_path.unlink()  # Remove expired cache
                return None

            # Load cached content
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
                logger.info(f"Cache hit for {section_name}")
                return cached_data['content']

        except Exception as e:
            logger.warning(f"Error reading cache for {section_name}: {str(e)}")
            return None

    def set(self, template_type: str, section_name: str, prompt: str, content: str) -> None:
        """Store content in cache"""
        try:
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            cache_key = self._get_cache_key(template_type, section_name, prompt_hash)
            cache_path = self._get_cache_path(cache_key)

            cache_data = {
                'content': content,
                'timestamp': datetime.now().isoformat(),
                'template_type': template_type,
                'section_name': section_name
            }

            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
                logger.debug(f"Cached content for {section_name}")

        except Exception as e:
            logger.warning(f"Error caching content for {section_name}: {str(e)}")


class SOPGenerator:
    """Enhanced SOP template generator with caching, retry logic, and progress tracking"""

    def __init__(self, template_type: str, industry_data: Dict = None):
        """
        Initialize the SOP generator with enhanced features

        Args:
            template_type: Type of SOP template (restaurant, healthcare, etc.)
            industry_data: Optional industry-specific data
        """
        self.template_type = template_type
        self.industry_data = industry_data or {}

        # Initialize cache
        cache_duration = int(os.getenv('CACHE_DURATION_HOURS', 24))
        self.cache = TemplateCache(cache_duration_hours=cache_duration)

        # Load configuration data
        self.compliance_data = self.load_compliance_requirements()
        self.prompts = self.load_prompts()

        # Initialize Free LLM client with multiple providers
        try:
            self.llm_client = FreeLLMClient()
            available_providers = self.llm_client.get_available_providers()

            if available_providers:
                logger.info(f"✅ LLM client initialized with providers: {available_providers}")
                self.use_hardcoded_content = False
            else:
                logger.warning("⚠️ No LLM providers configured - will use hardcoded content")
                self.use_hardcoded_content = True
                self.llm_client = None

        except Exception as e:
            logger.error(f"❌ Failed to initialize LLM client: {e}")
            logger.warning("Falling back to hardcoded content")
            self.use_hardcoded_content = True
            self.llm_client = None

        # Setup Jinja2 for template rendering
        self.template_env = Environment(
            loader=FileSystemLoader('templates/'),
            autoescape=True
        )

        # Configuration
        self.max_retries = int(os.getenv('MAX_API_RETRIES', 3))
        self.use_hardcoded_content = os.getenv('USE_HARDCODED_CONTENT', 'False').lower() == 'true'

        logger.info(f"SOPGenerator initialized for {template_type} with caching enabled")

    def load_compliance_requirements(self) -> Dict:
        """Load compliance requirements from data files with error handling"""
        compliance_file = f"data/compliance/{self.template_type}.yaml"
        try:
            if os.path.exists(compliance_file):
                with open(compliance_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    logger.info(f"Loaded compliance data for {self.template_type}")
                    return data or {}
            else:
                logger.warning(f"Compliance file not found: {compliance_file}")
                return self._get_default_compliance_data()
        except Exception as e:
            logger.error(f"Error loading compliance requirements: {str(e)}")
            return self._get_default_compliance_data()

    def load_prompts(self) -> Dict:
        """Load AI prompts for content generation with error handling"""
        prompt_file = f"prompts/{self.template_type}_prompts.json"
        try:
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded prompts for {self.template_type}")
                    return data
            else:
                logger.warning(f"Prompt file not found: {prompt_file}")
                return self._get_default_prompts()
        except Exception as e:
            logger.error(f"Error loading prompts: {str(e)}")
            return self._get_default_prompts()

    def _get_default_compliance_data(self) -> Dict:
        """Return default compliance data structure"""
        return {
            'sections': [
                {'name': 'Introduction', 'order': 1, 'required': True},
                {'name': 'Procedures', 'order': 2, 'required': True},
                {'name': 'Compliance Requirements', 'order': 3, 'required': True},
                {'name': 'Documentation', 'order': 4, 'required': True}
            ],
            'standards': ['ISO 9001', 'Industry Best Practices'],
            'regulatory_links': {}
        }

    def _get_default_prompts(self) -> Dict:
        """Return default prompts for content generation"""
        return {
            'Introduction': {
                'base': 'Create a comprehensive introduction section for this SOP.'
            },
            'Procedures': {
                'base': 'Create detailed step-by-step procedures for this SOP.'
            },
            'Compliance Requirements': {
                'base': 'Create compliance requirements section for this SOP.'
            },
            'Documentation': {
                'base': 'Create documentation requirements section for this SOP.'
            }
        }

    def _call_llm_api(self, prompt: str, section_name: str) -> str:
        """Make API call to LLM providers with automatic fallback"""
        if not self.llm_client:
            raise ValueError("LLM client not initialized")

        try:
            system_prompt = "You are an expert in creating comprehensive, compliant SOPs."

            # Use the multi-provider LLM client (includes built-in retry logic)
            response = self.llm_client.generate_content(
                system_prompt=system_prompt,
                user_prompt=prompt
            )

            content = response.content
            if not content or len(content.strip()) < 50:
                raise ValueError(f"Generated content too short for {section_name}")

            # Log which provider was used
            logger.info(f"✅ Content generated using {response.provider} ({response.model})")
            if response.response_time:
                logger.debug(f"Response time: {response.response_time:.2f}s")

            return content

        except Exception as e:
            logger.error(f"❌ Error calling LLM API for {section_name}: {str(e)}")
            raise

    def generate_section(self, section_name: str, requirements: Dict) -> str:
        """
        Generate a single section using AI with caching and validation

        Args:
            section_name: Name of the section to generate
            requirements: Requirements dictionary for the section

        Returns:
            Generated section content as markdown string
        """
        logger.info(f"Generating section: {section_name}")

        # Build the prompt
        base_prompt = self.prompts.get(section_name, {}).get('base', '')
        compliance_reqs = requirements.get('compliance', [])

        prompt = f"""
        Create a detailed SOP section for {section_name}.

        Industry: {self.industry_data.get('name', 'General')}
        Template Type: {self.template_type}
        Compliance Requirements: {', '.join(compliance_reqs)}

        {base_prompt}

        Include:
        - Step-by-step procedures
        - Regulatory citations where applicable
        - Best practices and tips
        - Common mistakes to avoid
        - Required documentation
        - Quality checkpoints

        Format the response in markdown with clear headers and bullet points.
        Ensure the content is comprehensive and actionable.
        """

        # Check cache first
        cached_content = self.cache.get(self.template_type, section_name, prompt)
        if cached_content:
            logger.info(f"Using cached content for {section_name}")
            return cached_content

        # Use hardcoded content for MVP testing if enabled
        if self.use_hardcoded_content:
            content = self._get_hardcoded_content(section_name)
            self.cache.set(self.template_type, section_name, prompt, content)
            return content

        try:
            # Generate content using free LLM providers
            content = self._call_llm_api(prompt, section_name)

            # Validate generated content
            if not self._validate_section_content(section_name, content):
                logger.warning(f"Generated content for {section_name} failed validation")
                content = self._get_fallback_content(section_name)

            # Cache the generated content
            self.cache.set(self.template_type, section_name, prompt, content)

            logger.info(f"Successfully generated section: {section_name}")
            return content

        except Exception as e:
            logger.error(f"Error generating section {section_name}: {str(e)}")
            # Return fallback content instead of error message
            fallback_content = self._get_fallback_content(section_name)
            self.cache.set(self.template_type, section_name, prompt, fallback_content)
            return fallback_content

    def _validate_section_content(self, section_name: str, content: str) -> bool:
        """
        Validate generated section content

        Args:
            section_name: Name of the section
            content: Generated content to validate

        Returns:
            True if content is valid, False otherwise
        """
        if not content or len(content.strip()) < 100:
            logger.warning(f"Content too short for {section_name}")
            return False

        # Check for required elements based on section type
        required_elements = {
            'Introduction': ['purpose', 'scope', 'overview'],
            'Procedures': ['step', 'procedure', 'process'],
            'Compliance Requirements': ['requirement', 'regulation', 'standard'],
            'Documentation': ['document', 'record', 'form']
        }

        section_requirements = required_elements.get(section_name, [])
        content_lower = content.lower()

        # Check if at least one required element is present
        if section_requirements and not any(req in content_lower for req in section_requirements):
            logger.warning(f"Missing required elements in {section_name}")
            return False

        # Check for markdown formatting
        if not any(marker in content for marker in ['#', '*', '-', '1.']):
            logger.warning(f"Poor formatting in {section_name}")
            return False

        return True

    def _get_hardcoded_content(self, section_name: str) -> str:
        """
        Get hardcoded content for MVP testing

        Args:
            section_name: Name of the section

        Returns:
            Hardcoded content for the section
        """
        hardcoded_content = {
            'Introduction': f"""
# Introduction

## Purpose
This Standard Operating Procedure (SOP) provides comprehensive guidelines for {self.template_type} operations to ensure consistency, quality, and compliance with industry standards.

## Scope
This SOP applies to all staff members involved in {self.template_type} operations and covers all related processes and procedures.

## Overview
- Establishes clear operational procedures
- Ensures regulatory compliance
- Maintains quality standards
- Provides training guidelines
            """,
            'Procedures': f"""
# Standard Operating Procedures

## Core Procedures

### 1. Preparation Phase
- Review all requirements and documentation
- Ensure all necessary resources are available
- Verify compliance with current regulations
- Complete pre-operation checklist

### 2. Execution Phase
- Follow established protocols step-by-step
- Monitor quality at each checkpoint
- Document all activities and observations
- Address any deviations immediately

### 3. Completion Phase
- Conduct final quality review
- Complete all required documentation
- Store records according to retention policy
- Prepare for next operation cycle

## Quality Checkpoints
- Initial setup verification
- Mid-process quality check
- Final output validation
- Documentation review
            """,
            'Compliance Requirements': f"""
# Compliance Requirements

## Regulatory Standards
- Industry-specific regulations must be followed
- Regular compliance audits are required
- Staff training on compliance is mandatory
- Documentation must meet regulatory standards

## Quality Standards
- ISO 9001 quality management principles
- Industry best practices implementation
- Continuous improvement processes
- Customer satisfaction monitoring

## Documentation Requirements
- All procedures must be documented
- Records must be maintained for required periods
- Regular review and updates are necessary
- Access controls must be implemented
            """,
            'Documentation': f"""
# Documentation Requirements

## Required Documents
- Standard Operating Procedures
- Training records and certifications
- Quality control checklists
- Incident reports and corrective actions
- Audit reports and compliance records

## Record Keeping
- All records must be accurate and complete
- Digital and physical storage requirements
- Retention periods must be observed
- Regular backup and recovery procedures

## Review and Updates
- Annual review of all documentation
- Updates based on regulatory changes
- Version control and change management
- Staff notification of updates
            """
        }

        return hardcoded_content.get(section_name, f"# {section_name}\n\nContent for {section_name} section.")

    def _get_fallback_content(self, section_name: str) -> str:
        """
        Get fallback content when AI generation fails

        Args:
            section_name: Name of the section

        Returns:
            Fallback content for the section
        """
        return f"""
# {section_name}

## Overview
This section covers the {section_name.lower()} requirements for {self.template_type} operations.

## Key Points
- Follow established procedures
- Maintain quality standards
- Ensure compliance with regulations
- Document all activities

## Next Steps
- Review detailed procedures
- Complete required training
- Implement quality controls
- Monitor compliance

*Note: This is fallback content. Please review and customize based on specific requirements.*
        """

    def generate_template(self) -> Dict:
        """
        Generate complete SOP template with progress tracking and enhanced error handling

        Returns:
            Dictionary containing the complete generated template
        """
        start_time = datetime.now()
        logger.info(f"Starting generation for {self.template_type} template")

        template_structure = self.compliance_data.get('sections', [])
        if not template_structure:
            logger.warning("No sections found in compliance data, using defaults")
            template_structure = self._get_default_compliance_data()['sections']

        # Initialize template structure
        generated_content = {
            'metadata': {
                'type': self.template_type,
                'version': '1.0',
                'generated_date': datetime.now().isoformat(),
                'compliance_standards': self.compliance_data.get('standards', []),
                'industry_data': self.industry_data,
                'generation_method': 'hardcoded' if self.use_hardcoded_content else 'ai_generated'
            },
            'sections': {},
            'generation_stats': {
                'total_sections': len(template_structure),
                'successful_sections': 0,
                'failed_sections': 0,
                'cached_sections': 0
            }
        }

        # Sort sections by order
        template_structure.sort(key=lambda x: x.get('order', 999))

        # Generate each section with progress tracking
        print(f"\n🚀 Generating {self.template_type} SOP template...")
        print(f"📋 Total sections to generate: {len(template_structure)}")

        with tqdm(total=len(template_structure), desc="Generating sections", unit="section") as pbar:
            for i, section in enumerate(template_structure):
                section_name = section['name']
                pbar.set_description(f"Generating: {section_name}")

                try:
                    # Check if using cached content
                    prompt = f"dummy_prompt_for_cache_check_{section_name}"
                    is_cached = self.cache.get(self.template_type, section_name, prompt) is not None

                    section_content = self.generate_section(
                        section_name,
                        section.get('requirements', {})
                    )

                    generated_content['sections'][section_name] = {
                        'content': section_content,
                        'order': section.get('order', i + 1),
                        'required': section.get('required', True),
                        'generated_at': datetime.now().isoformat(),
                        'cached': is_cached
                    }

                    generated_content['generation_stats']['successful_sections'] += 1
                    if is_cached:
                        generated_content['generation_stats']['cached_sections'] += 1

                    pbar.set_postfix({
                        'Success': generated_content['generation_stats']['successful_sections'],
                        'Cached': generated_content['generation_stats']['cached_sections']
                    })

                except Exception as e:
                    logger.error(f"Failed to generate section {section_name}: {str(e)}")
                    generated_content['generation_stats']['failed_sections'] += 1

                    # Add error section
                    generated_content['sections'][section_name] = {
                        'content': self._get_fallback_content(section_name),
                        'order': section.get('order', i + 1),
                        'required': section.get('required', True),
                        'generated_at': datetime.now().isoformat(),
                        'error': str(e),
                        'cached': False
                    }

                pbar.update(1)

        # Add compliance tracking features
        try:
            generated_content['compliance_features'] = self.generate_compliance_features()
        except Exception as e:
            logger.error(f"Error generating compliance features: {str(e)}")
            generated_content['compliance_features'] = {}

        # Add interactive elements
        try:
            generated_content['interactive_elements'] = self.generate_interactive_elements()
        except Exception as e:
            logger.error(f"Error generating interactive elements: {str(e)}")
            generated_content['interactive_elements'] = []

        # Calculate generation time
        end_time = datetime.now()
        generation_time = (end_time - start_time).total_seconds()
        generated_content['generation_stats']['generation_time_seconds'] = generation_time

        # Log completion summary
        stats = generated_content['generation_stats']
        logger.info(f"Template generation complete for {self.template_type}")
        logger.info(f"Stats: {stats['successful_sections']}/{stats['total_sections']} successful, "
                   f"{stats['cached_sections']} cached, {stats['failed_sections']} failed")
        logger.info(f"Generation time: {generation_time:.2f} seconds")

        print(f"\n✅ Template generation complete!")
        print(f"📊 Success rate: {stats['successful_sections']}/{stats['total_sections']} sections")
        print(f"⚡ Generation time: {generation_time:.2f} seconds")

        return generated_content

    def generate_compliance_features(self) -> Dict:
        """Generate compliance-specific features"""
        features = {
            'audit_trail': {
                'enabled': True,
                'fields': ['user', 'timestamp', 'action', 'section']
            },
            'version_control': {
                'enabled': True,
                'auto_increment': True
            },
            'regulatory_links': self.compliance_data.get('regulatory_links', {}),
            'update_notifications': {
                'enabled': True,
                'frequency': 'monthly'
            }
        }
        return features

    def generate_interactive_elements(self) -> List[Dict]:
        """Generate interactive elements for the template"""
        elements = []

        # Add QR codes for regulatory links
        for reg_name, reg_url in self.compliance_data.get('regulatory_links', {}).items():
            elements.append({
                'type': 'qr_code',
                'data': reg_url,
                'label': f"Scan for latest {reg_name} requirements"
            })

        # Add checklists
        for section in self.compliance_data.get('sections', []):
            if section.get('has_checklist', False):
                elements.append({
                    'type': 'checklist',
                    'section': section['name'],
                    'items': section.get('checklist_items', [])
                })

        return elements

    def save_template(self, content: Dict, output_path: str = None) -> str:
        """
        Save generated template to file with enhanced error handling

        Args:
            content: Template content to save
            output_path: Optional custom output path

        Returns:
            Path to the saved file
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_dir = os.getenv('LOCAL_STORAGE_PATH', './outputs')
                output_path = f"{output_dir}/templates/{self.template_type}_{timestamp}.json"

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Add file metadata
            content['file_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'file_path': output_path,
                'file_size_bytes': 0,  # Will be updated after saving
                'generator_version': '2.0'
            }

            # Save with pretty formatting
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)

            # Update file size
            file_size = os.path.getsize(output_path)
            content['file_metadata']['file_size_bytes'] = file_size

            # Re-save with updated metadata
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)

            logger.info(f"Template saved to {output_path} ({file_size} bytes)")
            return output_path

        except Exception as e:
            logger.error(f"Error saving template: {str(e)}")
            raise


def main():
    """Enhanced main execution function with better error handling and options"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='Enhanced SOP Template Generator with caching and retry logic',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate restaurant SOP with hardcoded content (for testing)
  python sop_generator.py --type restaurant --hardcoded

  # Generate healthcare SOP with AI (requires API key)
  python sop_generator.py --type healthcare --industry-data '{"name": "Hospital"}'

  # Generate with custom output path
  python sop_generator.py --type restaurant --output ./my_sop.json
        """
    )

    parser.add_argument(
        '--type',
        required=True,
        choices=['restaurant', 'healthcare', 'it-onboarding', 'customer-service'],
        help='Type of SOP template to generate'
    )
    parser.add_argument(
        '--output',
        help='Output file path (default: auto-generated in outputs/templates/)'
    )
    parser.add_argument(
        '--industry-data',
        type=str,
        help='Industry-specific data as JSON string'
    )
    parser.add_argument(
        '--hardcoded',
        action='store_true',
        help='Use hardcoded content instead of AI generation (for testing)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching (force regeneration)'
    )

    args = parser.parse_args()

    # Set environment variables based on arguments
    if args.hardcoded:
        os.environ['USE_HARDCODED_CONTENT'] = 'True'

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse industry data
    industry_data = {}
    if args.industry_data:
        try:
            industry_data = json.loads(args.industry_data)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing industry data JSON: {e}")
            sys.exit(1)

    try:
        print(f"🏗️  Initializing SOP Generator for {args.type}...")

        # Initialize generator
        generator = SOPGenerator(args.type, industry_data)

        # Clear cache if requested
        if args.no_cache:
            print("🗑️  Clearing cache...")
            import shutil
            if generator.cache.cache_dir.exists():
                shutil.rmtree(generator.cache.cache_dir)
                generator.cache.cache_dir.mkdir(exist_ok=True)

        # Generate template
        print(f"⚙️  Starting template generation...")
        template_content = generator.generate_template()

        # Save template
        print(f"💾 Saving template...")
        output_path = generator.save_template(template_content, args.output)

        # Print success summary
        stats = template_content.get('generation_stats', {})
        print(f"\n🎉 Template generated successfully!")
        print(f"📁 Output file: {output_path}")
        print(f"📊 Generation stats:")
        print(f"   • Total sections: {stats.get('total_sections', 'N/A')}")
        print(f"   • Successful: {stats.get('successful_sections', 'N/A')}")
        print(f"   • From cache: {stats.get('cached_sections', 'N/A')}")
        print(f"   • Failed: {stats.get('failed_sections', 'N/A')}")
        print(f"   • Generation time: {stats.get('generation_time_seconds', 'N/A')}s")

        if stats.get('failed_sections', 0) > 0:
            print(f"\n⚠️  Warning: {stats['failed_sections']} sections used fallback content")
            print("   Check the logs for details and consider reviewing the output")

    except KeyboardInterrupt:
        print(f"\n⏹️  Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error during template generation: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        print("   Check the logs for more details")
        sys.exit(1)


if __name__ == "__main__":
    main()
