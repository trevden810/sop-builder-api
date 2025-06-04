"""
Multi-Provider LLM Client for Free API Services
Supports Groq, Hugging Face, Together AI with automatic fallback
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    TOGETHER = "together"
    OPENROUTER = "openrouter"
    AUTO = "auto"

@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    cost: float = 0.0
    response_time: float = 0.0

class FreeLLMClient:
    """
    Multi-provider LLM client that automatically tries free APIs in order:
    1. Groq (fastest, free tier)
    2. Hugging Face (300 req/hour free)
    3. Together AI ($25 free credits)
    4. OpenRouter (free DeepSeek V3 access)
    """

    def __init__(self):
        self.providers = {
            LLMProvider.GROQ: self._init_groq(),
            LLMProvider.HUGGINGFACE: self._init_huggingface(),
            LLMProvider.TOGETHER: self._init_together(),
            LLMProvider.OPENROUTER: self._init_openrouter()
        }

        # Configuration from environment
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '2000'))
        self.temperature = float(os.getenv('LLM_TEMPERATURE', '0.7'))
        self.timeout = int(os.getenv('LLM_TIMEOUT', '30'))
        self.retry_attempts = int(os.getenv('LLM_RETRY_ATTEMPTS', '3'))

        # Provider priority order
        self.provider_order = [LLMProvider.GROQ, LLMProvider.HUGGINGFACE, LLMProvider.TOGETHER, LLMProvider.OPENROUTER]

        logger.info("FreeLLMClient initialized with providers: %s",
                   [p.value for p in self.provider_order if self.providers[p]['enabled']])

    def _init_groq(self) -> Dict[str, Any]:
        """Initialize Groq provider (OpenAI-compatible)"""
        api_key = os.getenv('GROQ_API_KEY', '').strip()
        return {
            'enabled': bool(api_key and api_key != 'your_groq_api_key_here'),
            'api_key': api_key,
            'model': os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile'),
            'base_url': os.getenv('GROQ_BASE_URL', 'https://api.groq.com/openai/v1'),
            'headers': {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        }

    def _init_huggingface(self) -> Dict[str, Any]:
        """Initialize Hugging Face provider"""
        api_token = os.getenv('HUGGINGFACE_API_TOKEN', '').strip()
        return {
            'enabled': bool(api_token and api_token != 'your_huggingface_token_here'),
            'api_token': api_token,
            'model': os.getenv('HUGGINGFACE_MODEL', 'microsoft/DialoGPT-large'),
            'base_url': os.getenv('HUGGINGFACE_BASE_URL', 'https://api-inference.huggingface.co/models'),
            'headers': {
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json'
            }
        }

    def _init_together(self) -> Dict[str, Any]:
        """Initialize Together AI provider (OpenAI-compatible)"""
        api_key = os.getenv('TOGETHER_API_KEY', '').strip()
        return {
            'enabled': bool(api_key and api_key != 'your_together_api_key_here'),
            'api_key': api_key,
            'model': os.getenv('TOGETHER_MODEL', 'meta-llama/Llama-3-70b-chat-hf'),
            'base_url': os.getenv('TOGETHER_BASE_URL', 'https://api.together.xyz/v1'),
            'headers': {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        }

    def _init_openrouter(self) -> Dict[str, Any]:
        """Initialize OpenRouter provider (OpenAI-compatible)"""
        api_key = os.getenv('OPENROUTER_API_KEY', '').strip()
        return {
            'enabled': bool(api_key and api_key != 'your_openrouter_api_key_here' and api_key.startswith('sk-or-')),
            'api_key': api_key,
            'model': os.getenv('OPENROUTER_MODEL', 'deepseek/deepseek-chat'),
            'base_url': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
            'headers': {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/trevden810/SOP-Builder-MVP',  # Optional: for analytics
                'X-Title': 'SOP Builder MVP'  # Optional: for analytics
            }
        }

    def generate_content(self,
                        system_prompt: str,
                        user_prompt: str,
                        provider: Optional[LLMProvider] = None) -> LLMResponse:
        """
        Generate content using the specified provider or auto-fallback

        Args:
            system_prompt: System instruction for the LLM
            user_prompt: User's content request
            provider: Specific provider to use, or None for auto-fallback

        Returns:
            LLMResponse with generated content and metadata
        """

        if provider and provider != LLMProvider.AUTO:
            # Use specific provider
            return self._try_provider(provider, system_prompt, user_prompt)

        # Auto-fallback: try providers in order
        last_error = None
        for provider in self.provider_order:
            if not self.providers[provider]['enabled']:
                logger.debug(f"Skipping {provider.value} - not configured")
                continue

            try:
                logger.info(f"Trying provider: {provider.value}")
                response = self._try_provider(provider, system_prompt, user_prompt)
                logger.info(f"✅ Success with {provider.value}")
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"❌ {provider.value} failed: {str(e)}")
                continue

        # All providers failed - return fallback content
        logger.error("All LLM providers failed, using fallback content")
        return self._get_fallback_response(user_prompt, last_error)

    def _try_provider(self, provider: LLMProvider, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Try a specific provider with retry logic"""

        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()

                if provider == LLMProvider.GROQ:
                    response = self._call_groq(system_prompt, user_prompt)
                elif provider == LLMProvider.HUGGINGFACE:
                    response = self._call_huggingface(system_prompt, user_prompt)
                elif provider == LLMProvider.TOGETHER:
                    response = self._call_together(system_prompt, user_prompt)
                elif provider == LLMProvider.OPENROUTER:
                    response = self._call_openrouter(system_prompt, user_prompt)
                else:
                    raise ValueError(f"Unknown provider: {provider}")

                response.response_time = time.time() - start_time
                response.provider = provider.value

                return response

            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed for {provider.value}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise e

    def _call_groq(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call Groq API (OpenAI-compatible)"""
        config = self.providers[LLMProvider.GROQ]

        payload = {
            "model": config['model'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=config['headers'],
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data['choices'][0]['message']['content'],
            provider=LLMProvider.GROQ.value,
            model=config['model'],
            tokens_used=data.get('usage', {}).get('total_tokens', 0)
        )

    def _call_huggingface(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call Hugging Face Inference API"""
        config = self.providers[LLMProvider.HUGGINGFACE]

        # Combine prompts for HF format
        combined_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"

        payload = {
            "inputs": combined_prompt,
            "parameters": {
                "max_new_tokens": self.max_tokens,
                "temperature": self.temperature,
                "return_full_text": False
            }
        }

        response = requests.post(
            f"{config['base_url']}/{config['model']}",
            headers=config['headers'],
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        # Handle different response formats
        if isinstance(data, list) and len(data) > 0:
            content = data[0].get('generated_text', '')
        else:
            content = data.get('generated_text', str(data))

        return LLMResponse(
            content=content,
            provider=LLMProvider.HUGGINGFACE.value,
            model=config['model'],
            tokens_used=len(content.split())  # Approximate
        )

    def _call_together(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call Together AI API (OpenAI-compatible)"""
        config = self.providers[LLMProvider.TOGETHER]

        payload = {
            "model": config['model'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=config['headers'],
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data['choices'][0]['message']['content'],
            provider=LLMProvider.TOGETHER.value,
            model=config['model'],
            tokens_used=data.get('usage', {}).get('total_tokens', 0)
        )

    def _call_openrouter(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call OpenRouter API (OpenAI-compatible)"""
        config = self.providers[LLMProvider.OPENROUTER]

        payload = {
            "model": config['model'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=config['headers'],
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data['choices'][0]['message']['content'],
            provider=LLMProvider.OPENROUTER.value,
            model=config['model'],
            tokens_used=data.get('usage', {}).get('total_tokens', 0)
        )

    def _get_fallback_response(self, user_prompt: str, error: Exception) -> LLMResponse:
        """Generate fallback content when all providers fail"""

        # Extract section type from prompt
        section_type = "general"
        if "introduction" in user_prompt.lower():
            section_type = "introduction"
        elif "daily" in user_prompt.lower() or "procedure" in user_prompt.lower():
            section_type = "daily_procedures"
        elif "crisis" in user_prompt.lower() or "emergency" in user_prompt.lower():
            section_type = "crisis_response"
        elif "training" in user_prompt.lower():
            section_type = "employee_training"
        elif "monitoring" in user_prompt.lower():
            section_type = "monitoring"
        elif "documentation" in user_prompt.lower():
            section_type = "documentation"

        fallback_content = self._get_fallback_content_by_type(section_type)

        return LLMResponse(
            content=fallback_content,
            provider="fallback",
            model="local_template",
            tokens_used=len(fallback_content.split()),
            cost=0.0
        )

    def _get_fallback_content_by_type(self, section_type: str) -> str:
        """Get high-quality fallback content by section type"""

        fallback_templates = {
            "introduction": """
# Introduction to Food Safety Management

## Overview
This Standard Operating Procedure (SOP) establishes comprehensive food safety protocols for restaurant operations to ensure compliance with health regulations and protect customer welfare.

## Importance of Food Safety
- **Public Health Protection**: Prevents foodborne illnesses that affect millions annually
- **Legal Compliance**: Meets FDA Food Code and local health department requirements
- **Business Protection**: Reduces liability and maintains reputation
- **Operational Excellence**: Ensures consistent quality and customer satisfaction

## Key Statistics
- Foodborne illnesses affect 48 million Americans annually (CDC, 2023)
- Proper food safety procedures reduce contamination risk by 85%
- Restaurants with strong food safety programs see 40% fewer health violations

## Regulatory Framework
- **FDA Food Code**: Federal guidelines for food service establishments
- **HACCP Principles**: Hazard Analysis Critical Control Points system
- **Local Health Codes**: Municipality-specific requirements
- **OSHA Standards**: Workplace safety in food service environments

## Implementation Requirements
- All staff must complete food safety training within 30 days of hire
- Management must maintain current food safety certifications
- Daily monitoring and documentation of critical control points
- Regular internal audits and corrective action procedures
            """,

            "daily_procedures": """
# Daily Food Safety Procedures

## Opening Procedures

### Equipment Verification (6:00 AM - 6:30 AM)
1. **Temperature Checks**
   - Refrigeration units: 35-38°F (walk-in coolers)
   - Freezer units: 0-5°F (all freezers)
   - Hot holding equipment: 140°F minimum
   - Document all temperatures on daily log

2. **Equipment Inspection**
   - Verify proper operation of dishwashing equipment
   - Check sanitizer concentration (200-400 ppm chlorine)
   - Inspect food preparation surfaces for cleanliness
   - Test probe thermometers for accuracy

3. **Staff Health Screening**
   - Visual health assessment for all employees
   - Temperature checks if illness symptoms present
   - Review exclusion criteria (fever, vomiting, diarrhea)
   - Document health screening results

## Closing Procedures

### Sanitation and Security (9:00 PM - 10:00 PM)
1. **Final Temperature Documentation**
   - Record all refrigeration unit temperatures
   - Verify proper cooling of hot foods
   - Check freezer temperatures and door seals

2. **Cleaning and Sanitization**
   - Complete cleaning of all food contact surfaces
   - Sanitize cutting boards and utensils
   - Empty and clean grease traps
   - Secure all food storage areas

## Quality Checkpoints
- ✅ All temperatures within safe ranges
- ✅ Staff health screening completed
- ✅ Equipment functioning properly
- ✅ Cleaning logs completed and signed
            """,

            "crisis_response": """
# Emergency Response Procedures

## Foodborne Illness Response

### Immediate Actions (0-2 Hours)
1. **Customer Safety**
   - Isolate suspected contaminated food immediately
   - Provide medical assistance if needed
   - Document customer complaints and symptoms
   - Contact emergency services if severe symptoms present

2. **Investigation Protocol**
   - Preserve suspected food samples for testing
   - Review preparation logs and temperatures
   - Interview staff involved in food preparation
   - Document timeline of events

3. **Regulatory Notification**
   - Contact local health department within 2 hours
   - Notify management and corporate office
   - Prepare incident report documentation
   - Coordinate with health officials for investigation

## Power Outage Procedures

### Equipment Protection
1. **Immediate Response**
   - Keep refrigeration doors closed
   - Monitor internal temperatures every 30 minutes
   - Use backup thermometers if available
   - Document temperature readings

2. **Food Safety Decisions**
   - Discard perishables if temperature exceeds 41°F for >4 hours
   - Transfer critical items to backup refrigeration if available
   - Implement emergency menu with shelf-stable items
   - Document all food disposal decisions

## Contamination Events

### Chemical Contamination
1. **Immediate Isolation**
   - Remove all affected food from service
   - Evacuate area if chemical spill present
   - Ventilate area and ensure staff safety
   - Contact poison control if exposure occurs

2. **Cleanup Protocol**
   - Use appropriate PPE for cleanup
   - Follow chemical-specific cleanup procedures
   - Test area for residual contamination
   - Document incident and corrective actions

## Communication Plan
- **Internal**: Manager → Staff → Corporate
- **External**: Health Department → Customers → Media (if required)
- **Documentation**: Incident reports, corrective actions, follow-up
            """,

            "employee_training": """
# Employee Food Safety Training Program

## Initial Training Requirements

### New Employee Orientation (Week 1)
1. **Food Safety Fundamentals**
   - Personal hygiene requirements
   - Handwashing procedures (20-second minimum)
   - Proper use of gloves and utensils
   - Temperature danger zone (41°F - 135°F)

2. **Hands-On Training**
   - Proper handwashing demonstration
   - Thermometer use and calibration
   - Cross-contamination prevention
   - Cleaning and sanitizing procedures

3. **Certification Requirements**
   - Complete food handler certification within 30 days
   - Pass written exam with 80% minimum score
   - Demonstrate practical skills competency
   - Maintain certification records in personnel file

## Ongoing Education Program

### Monthly Training Topics
- **January**: Personal Hygiene and Health Policies
- **February**: Temperature Control and Monitoring
- **March**: Cross-Contamination Prevention
- **April**: Cleaning and Sanitization
- **May**: Allergen Management
- **June**: HACCP Principles

### Training Methods
1. **Interactive Sessions**
   - Group discussions and case studies
   - Hands-on demonstrations
   - Video training modules
   - Competency assessments

2. **Documentation Requirements**
   - Training attendance records
   - Competency evaluation forms
   - Certification tracking
   - Corrective action plans

## Performance Monitoring

### Daily Observations
- Proper handwashing frequency
- Correct glove usage
- Temperature monitoring compliance
- Cleaning procedure adherence

### Monthly Evaluations
- Written knowledge assessments
- Practical skill demonstrations
- Customer service integration
- Corrective action follow-up

## Training Resources
- FDA Food Code guidelines
- ServSafe certification materials
- Company-specific procedures
- Industry best practice guides
            """
        }

        return fallback_templates.get(section_type, fallback_templates["introduction"])

    def get_available_providers(self) -> List[str]:
        """Get list of currently available providers"""
        return [provider.value for provider, config in self.providers.items() if config['enabled']]

    def test_providers(self) -> Dict[str, bool]:
        """Test all configured providers"""
        results = {}
        test_prompt = "Hello, please respond with 'OK' to confirm you're working."

        for provider in self.provider_order:
            if not self.providers[provider]['enabled']:
                results[provider.value] = False
                continue

            try:
                response = self._try_provider(provider, "You are a helpful assistant.", test_prompt)
                results[provider.value] = bool(response.content)
                logger.info(f"✅ {provider.value} test successful")
            except Exception as e:
                results[provider.value] = False
                logger.error(f"❌ {provider.value} test failed: {e}")

        return results
