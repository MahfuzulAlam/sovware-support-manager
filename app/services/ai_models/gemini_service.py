"""Gemini model service via Google Generative AI for Tier 2/3 fallbacks."""

import logging

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Google Gemini models for Tier 2/3 fallbacks."""

    def __init__(self) -> None:
        self.configured = False
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.configured = True
        self.flash_model = "gemini-1.5-flash"
        self.pro_model = "gemini-1.5-pro"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a response from Gemini.

        Args:
            system_prompt: System instruction
            user_prompt: User query with context
            model: Model name (gemini-1.5-flash or gemini-1.5-pro)
            temperature: Sampling temperature
            max_tokens: Max output tokens

        Returns:
            Generated text response

        Raises:
            Exception: On Google Gemini API errors
        """
        if not self.configured:
            raise ValueError("GEMINI_API_KEY is required for Gemini service")
        try:
            logger.info("Gemini generate request (model=%s, max_tokens=%d)", model, max_tokens)
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            client = genai.GenerativeModel(model)
            response = await client.generate_content_async(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            content = response.text or ""
            return content.strip()
        except Exception as e:
            logger.error("Google Gemini API error (model=%s): %s", model, e)
            raise


gemini_service = GeminiService()
