"""API routes for translating thread content to English."""

import re
import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.evaluation import EvaluationRequest
from app.services.helpscout import helpscout_service
from app.services.translation_service import translation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["translate"])


class TranslateEnglishResponse(BaseModel):
    """Response schema for translate/english endpoint."""

    translation: str = Field(..., description="Translated text in English")
    note_saved: bool = Field(..., description="Whether the translation was saved as a note on the conversation")


def _extract_thread_body(thread_data: dict) -> str:
    """Extract plain text from a Help Scout thread (strip HTML)."""
    body = thread_data.get("body") or ""
    if isinstance(body, str):
        body = re.sub(r"<[^>]+>", "", body)
    return (body or "").strip()


@router.post(
    "/english",
    response_model=TranslateEnglishResponse,
    status_code=status.HTTP_200_OK,
    summary="Translate thread to English",
    description="Get the specified thread from a Help Scout conversation, translate its content to English using the configured Groq model, and add the translation as a note on the conversation.",
)
async def translate_thread_to_english(request: EvaluationRequest) -> TranslateEnglishResponse:
    """
    Translate a Help Scout thread to English and add the translation as a note.

    1. Fetches the conversation with embedded threads from Help Scout.
    2. Finds the thread by thread_id.
    3. Translates the thread body to English via Groq (GROQ_TRANSLATE_MODEL).
    4. Saves the translation as a note on the same conversation.
    """
    try:
        logger.info(
            "Translating thread %s in conversation %s to English",
            request.thread_id,
            request.conversation_id,
        )

        # Fetch conversation with embedded threads
        try:
            conversation_data = await helpscout_service.get_conversation(
                request.conversation_id, embed_threads=True
            )
        except Exception as e:
            logger.error("Failed to fetch conversation from Help Scout: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch conversation from Help Scout: {e!s}",
            ) from e

        # Find the specific thread
        thread_data = None
        if "_embedded" in conversation_data and "threads" in conversation_data["_embedded"]:
            threads = conversation_data["_embedded"]["threads"]
            try:
                thread_id_int = int(request.thread_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid thread_id format: {request.thread_id}. Must be a number.",
                ) from None
            for thread in threads:
                if thread.get("id") == thread_id_int:
                    thread_data = thread
                    break

        if not thread_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {request.thread_id} not found in conversation {request.conversation_id}",
            )

        # Extract plain text from thread
        text_to_translate = _extract_thread_body(thread_data)
        if not text_to_translate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread has no body text to translate.",
            )

        # If already English, stop: no translation, no note
        if translation_service.detect_language(text_to_translate) == "en":
            logger.info("Thread content is English; skipping translation and note for conversation %s", request.conversation_id)
            return TranslateEnglishResponse(translation="", note_saved=False)

        # Translate via Groq
        try:
            translation = await translation_service.translate_to_english(text_to_translate)
        except Exception as e:
            logger.error("Groq translate failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Translation failed: {e!s}",
            ) from e

        # Only add note when we have a non-empty translation (empty = already English or AI said so)
        note_saved = False
        # if translation:
        #     note_body = f"---\nTranslation to English\n---\n\n{translation}"
        #     try:
        #         await helpscout_service.create_note(request.conversation_id, note_body)
        #         note_saved = True
        #         logger.info("Translation note saved to conversation %s", request.conversation_id)
        #     except Exception as e:
        #         logger.warning(
        #             "Failed to save translation note to conversation %s: %s",
        #             request.conversation_id,
        #             e,
        #         )

        return TranslateEnglishResponse(translation=translation, note_saved=note_saved)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in translate_thread_to_english: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e!s}",
        ) from e
