"""Claude model service via Anthropic for Tier 4 (custom code / development) queries."""

import logging
from typing import Optional

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeService:
    """Claude models via Anthropic for Tier 4 code generation and development queries."""

    def __init__(self) -> None:
        self.client: Optional[AsyncAnthropic] = None
        if settings.anthropic_api_key:
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"  # claude-sonnet-4-5 alias

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.5,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a response from Claude via Anthropic.

        Args:
            system_prompt: System instruction
            user_prompt: User query with context
            temperature: Sampling temperature
            max_tokens: Max tokens in response

        Returns:
            Generated text response

        Raises:
            Exception: On Anthropic API errors
        """
        if not self.client:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude service")
        try:
            logger.info("Claude generate request (model=%s, max_tokens=%d)", self.model, max_tokens)
            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response.content and len(response.content) > 0:
                content = response.content[0].text or ""
                return content.strip()
            return ""
        except Exception as e:
            logger.error("Anthropic Claude API error: %s", e)
            raise


claude_service = ClaudeService()
