"""OpenAI client for LLM interactions."""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import openai
from openai import OpenAI


logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class LLMClient:
    """OpenAI client for generating code suggestions."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        """Initialize the LLM client.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name to use
            base_url: Base URL for API (for custom endpoints)
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation (0.0 = deterministic)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            
        self.client = OpenAI(**client_kwargs)
        logger.info(f"Initialized LLM client with model: {self.model}")
    
    async def generate_suggestions(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_json_mode: bool = True,
        **kwargs
    ) -> LLMResponse:
        """Generate code suggestions based on analysis findings.
        
        Args:
            prompt: User prompt with analysis findings
            system_prompt: Optional system prompt for instructions
            use_json_mode: Whether to use JSON mode for structured output
            **kwargs: Additional parameters for the API call
            
        Returns:
            LLM response with suggestions
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({"role": "user", "content": prompt})
        
        # Merge kwargs with defaults
        api_params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            **kwargs
        }
        
        # Add JSON mode if supported and requested
        if use_json_mode and self._supports_json_mode():
            api_params["response_format"] = {"type": "json_object"}
        
        try:
            logger.info(f"Sending request to {self.model} (JSON mode: {use_json_mode and self._supports_json_mode()})")
            response = self.client.chat.completions.create(**api_params)
            
            # Extract response content
            choice = response.choices[0]
            content = choice.message.content or ""
            
            # Extract usage information
            usage = response.usage.model_dump() if response.usage else None
            
            logger.info(f"Received response with {len(content)} characters")
            if usage:
                logger.info(f"Token usage: {usage}")
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=choice.finish_reason,
            )
            
        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling LLM: {e}")
            raise
    
    def generate_suggestions_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_json_mode: bool = True,
        **kwargs
    ) -> LLMResponse:
        """Synchronous version of generate_suggestions.
        
        Args:
            prompt: User prompt with analysis findings
            system_prompt: Optional system prompt for instructions
            use_json_mode: Whether to use JSON mode for structured output
            **kwargs: Additional parameters for the API call
            
        Returns:
            LLM response with suggestions
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({"role": "user", "content": prompt})
        
        # Merge kwargs with defaults
        api_params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            **kwargs
        }
        
        # Add JSON mode if supported and requested
        if use_json_mode and self._supports_json_mode():
            api_params["response_format"] = {"type": "json_object"}
        
        try:
            logger.info(f"Sending request to {self.model} (JSON mode: {use_json_mode and self._supports_json_mode()})")
            response = self.client.chat.completions.create(**api_params)
            
            # Extract response content
            choice = response.choices[0]
            content = choice.message.content or ""
            
            # Extract usage information
            usage = response.usage.model_dump() if response.usage else None
            
            logger.info(f"Received response with {len(content)} characters")
            if usage:
                logger.info(f"Token usage: {usage}")
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=choice.finish_reason,
            )
            
        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling LLM: {e}")
            raise
    
    def _supports_json_mode(self) -> bool:
        """Check if the current model supports JSON mode.
        
        Returns:
            True if JSON mode is supported, False otherwise
        """
        # Models that support JSON mode (as of 2024)
        json_supported_models = [
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-4-1106-preview",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo",
        ]
        
        return any(supported_model in self.model for supported_model in json_supported_models)
    
    def validate_api_key(self) -> bool:
        """Validate that the API key works.
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Make a minimal API call to test the key
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False
