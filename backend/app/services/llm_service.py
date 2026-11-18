"""
LLM Service for AI-powered analysis and explanations.
Supports both Ollama (local) and OpenAI (cloud) providers.
"""

import os
import json
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM providers (Ollama/OpenAI)."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.ollama_base_url = settings.OLLAMA_BASE_URL
        self.openai_api_key = settings.OPENAI_API_KEY
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_base_url = settings.GROQ_BASE_URL

        # Initialize clients
        self._ollama_client = None
        self._openai_client = None
        self._groq_client = None

    def reload_configuration(self) -> Dict[str, str]:
        """Reload provider settings without restarting the API process."""
        from app.core.config import Settings

        refreshed = Settings()
        self.provider = refreshed.LLM_PROVIDER
        self.model = refreshed.LLM_MODEL
        self.ollama_base_url = refreshed.OLLAMA_BASE_URL
        self.openai_api_key = refreshed.OPENAI_API_KEY
        self.groq_api_key = refreshed.GROQ_API_KEY
        self.groq_base_url = refreshed.GROQ_BASE_URL
        self._ollama_client = None
        self._openai_client = None
        self._groq_client = None
        return {"provider": self.provider, "model": self.model}

    def _get_ollama_client(self):
        """Lazy initialization of Ollama client."""
        if self._ollama_client is None:
            try:
                import ollama
                self._ollama_client = ollama.Client(host=self.ollama_base_url)
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
                raise
        return self._ollama_client

    def _get_openai_client(self, api_key=None, base_url=None):
        """Lazy initialization of an OpenAI-compatible client."""
        if api_key is None:
            api_key = self.openai_api_key
        if base_url is None:
            base_url = None
        if base_url:
            if self._groq_client is None:
                from openai import OpenAI
                self._groq_client = OpenAI(api_key=api_key, base_url=base_url)
            return self._groq_client
        if self._openai_client is None:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
        return self._openai_client

    def is_available(self) -> bool:
        """Check if the configured LLM provider is available."""
        try:
            if self.provider == "ollama":
                client = self._get_ollama_client()
                models = client.list()
                return any(m['name'].startswith(self.model) for m in models.get('models', []))
            elif self.provider == "openai":
                return bool(self.openai_api_key)
            elif self.provider == "groq":
                if not self.groq_api_key or not self.model:
                    return False
                client = self._get_openai_client(self.groq_api_key, self.groq_base_url)
                models = client.models.list()
                return any(model.id == self.model for model in models.data)
        except Exception:
            return False
        return False

    def get_available_models(self) -> List[str]:
        """Get list of available models for the current provider."""
        try:
            if self.provider == "ollama":
                client = self._get_ollama_client()
                models = client.list()
                return [m['name'] for m in models.get('models', [])]
            elif self.provider == "openai":
                return ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            elif self.provider == "groq":
                client = self._get_openai_client(self.groq_api_key, self.groq_base_url)
                models = client.models.list()
                return sorted(model.id for model in models.data)

        except Exception:
            pass
        return []

    def generate(self,
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.3,
                 max_tokens: int = 2000) -> str:
        """Generate a completion from the LLM."""
        if self.provider == "ollama":
            return self._generate_ollama(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "openai":
            return self._generate_openai(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "groq":
            return self._generate_groq(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _generate_ollama(self,
                         prompt: str,
                         system_prompt: Optional[str],
                         temperature: float,
                         max_tokens: int) -> str:
        """Generate using Ollama."""
        client = self._get_ollama_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens
            }
        )
        return response['message']['content']

    def _generate_groq(self,
                       prompt: str,
                       system_prompt: Optional[str],
                       temperature: float,
                       max_tokens: int) -> str:
        """Generate using Groq's OpenAI-compatible API."""
        client = self._get_openai_client(self.groq_api_key, self.groq_base_url)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def _generate_openai(self,
                         prompt: str,
                         system_prompt: Optional[str],
                         temperature: float,
                         max_tokens: int) -> str:
        """Generate using OpenAI."""
        client = self._get_openai_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def generate_stream(self,
                              prompt: str,
                              system_prompt: Optional[str] = None,
                              temperature: float = 0.3,
                              max_tokens: int = 2000) -> AsyncGenerator[str, None]:
        """Generate a streaming completion from the LLM."""
        if self.provider == "ollama":
            async for chunk in self._generate_ollama_stream(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        elif self.provider == "openai":
            async for chunk in self._generate_openai_stream(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        elif self.provider == "groq":
            # The synchronous OpenAI-compatible client is used for MVP streaming support.
            yield self._generate_groq(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def _generate_ollama_stream(self,
                                      prompt: str,
                                      system_prompt: Optional[str],
                                      temperature: float,
                                      max_tokens: int) -> AsyncGenerator[str, None]:
        """Generate streaming using Ollama."""
        client = self._get_ollama_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens
            },
            stream=True
        )

        for chunk in stream:
            if 'message' in chunk and 'content' in chunk['message']:
                yield chunk['message']['content']

    async def _generate_openai_stream(self,
                                      prompt: str,
                                      system_prompt: Optional[str],
                                      temperature: float,
                                      max_tokens: int) -> AsyncGenerator[str, None]:
        """Generate streaming using OpenAI."""
        client = self._get_openai_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Prompt templates for different investigation types
class PromptTemplates:
    """Prompt templates for AI investigations."""

    ROOT_CAUSE_ANALYSIS = """You are a data quality expert analyzing root causes of data issues.

Given the following context:
- Dataset: {dataset_name} ({num_rows} rows, {num_cols} columns)
- Quality Findings: {findings_summary}
- User Query: {user_query}

Provide a structured root cause analysis:

1. **Primary Root Causes** - What are the most likely underlying causes?
2. **Contributing Factors** - What other factors may have contributed?
3. **Evidence** - What specific evidence from the findings supports each cause?
4. **Recommended Investigations** - What further analysis would confirm/refute these causes?

Format your response clearly with headers and bullet points."""

    PATTERN_ANALYSIS = """You are a data analyst identifying patterns in data quality issues.

Given:
- Dataset: {dataset_name} ({num_rows} rows, {num_cols} columns)
- Quality Findings: {findings_summary}
- User Query: {user_query}

Identify patterns in the data quality issues:

1. **Recurring Patterns** - What patterns appear across multiple columns/findings?
2. **Column Relationships** - Do issues in one column relate to issues in another?
3. **Systemic Issues** - Are there systemic problems (e.g., specific data source, time period)?
4. **Pattern Strength** - How strong/prevalent is each pattern?

Provide specific examples from the findings."""

    ANOMALY_DETECTION = """You are an anomaly detection specialist analyzing unusual data patterns.

Given:
- Dataset: {dataset_name} ({num_rows} rows, {num_cols} columns)
- Quality Findings: {findings_summary}
- User Query: {user_query}

Analyze for anomalies:

1. **Detected Anomalies** - What unusual patterns or outliers exist?
2. **Anomaly Types** - Categorize (point, contextual, collective)
3. **Potential Causes** - What could cause these anomalies?
4. **Severity Assessment** - How critical is each anomaly?
5. **Recommended Actions** - What should be investigated/fixed?

Reference specific findings and statistics."""

    IMPACT_ASSESSMENT = """You are a data risk analyst assessing the impact of data quality issues.

Given:
- Dataset: {dataset_name} ({num_rows} rows, {num_cols} columns)
- Quality Findings: {findings_summary}
- User Query: {user_query}

Assess the business impact:

1. **Affected Downstream Processes** - What analyses/reports/models use this data?
2. **Severity by Issue** - Rank issues by potential business impact
3. **Risk Scenarios** - What bad decisions could result from these issues?
4. **Mitigation Priority** - Which issues should be fixed first?
5. **Cost Estimation** - Rough estimate of effort to fix vs. risk of not fixing"""

    REPAIR_RECOMMENDATION = """You are a data repair specialist recommending repair strategies.

Given:
- Dataset: {dataset_name}
- Quality Finding: {finding_details}
- Available Repair Operations: {available_operations}
- Similar Past Repairs: {past_repairs}
- User Query: {user_query}

Recommend repair strategies:

1. **Recommended Strategy** - Primary recommendation with reasoning
2. **Alternative Strategies** - Other viable options
3. **Validation Plan** - How to verify the repair works
4. **Risks & Caveats** - What could go wrong
5. **Implementation Notes** - Specific parameters, order of operations

Reference similar past repairs if available."""


# Singleton instance
llm_service = LLMService()