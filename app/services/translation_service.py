"""Translation service: language detection and Groq-backed translation to English."""

import logging

from groq import AsyncGroq
from langdetect import LangDetectException, detect
from app.config import settings

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language code (e.g. 'en') for the given text. Returns empty string on failure."""
    if not text or not text.strip():
        return ""
    try:
        return detect(text)
    except LangDetectException as e:
        logger.debug("Langdetect failed: %s", e)
        return ""

# Prompt instructions so the AI keeps URLs, emails, and links unchanged
TRANSLATION_SYSTEM = """You are a translation engine.
Translate the input text into English.

STRICT RULES (must follow):
- Output ONLY the English translation. No titles, no notes, no quotes, no extra lines.
- Preserve line breaks and spacing exactly.
- DO NOT change any URLs, links, domains, paths, query strings, or fragments.
- DO NOT change any email addresses.
- If a line contains only a URL (or only an email), output it exactly unchanged.
- Keep punctuation style as close as possible to the original.
"""
TRANSLATION_USER_INSTRUCTION = """Task: Translate to English.

IMPORTANT:
1) Keep ALL URLs and emails EXACTLY as written.
2) Preserve formatting, including line breaks.
3) Do not add or remove content.
"""

class TranslationService:
    """Service for translation to English via Groq (and language detection)."""

    def __init__(self):
        """Initialize with Groq API credentials (translate model)."""
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    def detect_language(self, text: str) -> str:
        """Detect language code (e.g. 'en') for the given text. Returns empty string on failure."""
        return detect_language(text)

    async def translate_to_english(self, text: str) -> str:
        """
        Translate the given text to English using the Groq translate model.
        If the text is detected as English, returns empty string (no API call; caller should not add a note).

        Args:
            text: Text to translate (any language)

        Returns:
            Translated text in English, or empty string if already English (or AI returned empty)

        Raises:
            Exception: If Groq API call fails (when translation is needed)
        """
        if not text or not text.strip():
            return ""
        if detect_language(text) == "en":
            logger.info("Text already in English; returning empty (no note)")
            return ""
        model = settings.groq_translate_model
        prompt = f"""{TRANSLATION_USER_INSTRUCTION}

Text to translate:
{text}"""
        try:
            logger.info("Sending translate request to Groq (model=%s)", model)
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": TRANSLATION_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            out = (response.choices[0].message.content or "").strip()
            logger.info("Received translation from Groq")
            return out
        except Exception as e:
            logger.error("Groq translate API error: %s", e)
            raise


# Global service instance for translation
translation_service = TranslationService()
