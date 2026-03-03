"""Help Scout webhook endpoint."""

import hmac
import hashlib
import base64
import json
import re
import logging
from fastapi import APIRouter, Request, Response, status

from app.config import settings
from app.services.helpscout import helpscout_service
from app.services.translation_service import translation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

HELPSCOUT_EVENT_CUSTOMER_REPLY = "convo.customer.reply.created"


def _extract_thread_body(thread_data: dict) -> str:
    """Extract plain text from a Help Scout thread (strip HTML)."""
    body = thread_data.get("body") or ""
    if isinstance(body, str):
        body = re.sub(r"<[^>]+>", "", body)
    return (body or "").strip()


def _verify_helpscout_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify X-HelpScout-Signature using HMAC-SHA1 and the webhook secret."""
    if not secret or not signature:
        return False
    computed = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha1).digest()
    ).decode("ascii")
    return hmac.compare_digest(computed, signature.strip())


@router.post(
    "/helpscout",
    status_code=status.HTTP_200_OK,
    summary="Help Scout webhook",
    description="Receives Help Scout webhook events. On convo.customer.reply.created, translates the new customer reply to English and adds a note to the conversation.",
)
async def helpscout_webhook(request: Request) -> Response:
    """
    Handle Help Scout webhooks.

    - Verifies X-HelpScout-Signature when HELPSCOUT_WEBHOOK_SECRET is set.
    - Only processes convo.customer.reply.created: finds the latest customer thread,
      translates it to English via Groq, and adds the translation as a note.
    - Returns 2xx so Help Scout considers the delivery successful.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-HelpScout-Signature") or request.headers.get("x-helpscout-signature")
    event = request.headers.get("X-HelpScout-Event") or request.headers.get("x-helpscout-event")

    # Signature verification when secret is configured
    secret = settings.helpscout_webhook_secret
    if secret:
        if not signature:
            logger.warning("Help Scout webhook missing X-HelpScout-Signature header")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)
        if not _verify_helpscout_signature(body_bytes, signature, secret):
            logger.warning("Help Scout webhook signature verification failed")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    else:
        logger.debug("HELPSCOUT_WEBHOOK_SECRET not set; skipping signature verification")

    if event != HELPSCOUT_EVENT_CUSTOMER_REPLY:
        logger.info("Ignoring Help Scout event: %s", event)
        return Response(status_code=status.HTTP_200_OK)

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("Invalid webhook body: %s", e)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    conversation_id = payload.get("id")
    if conversation_id is None:
        logger.warning("Webhook payload missing conversation id")
        return Response(status_code=status.HTTP_200_OK)

    conversation_id = str(conversation_id)
    embedded = payload.get("_embedded") or {}
    threads = embedded.get("threads") or []
    customer_threads = [t for t in reversed(threads) if t.get("type") == "customer"]

    if not customer_threads:
        logger.info("No customer thread in webhook for conversation %s", conversation_id)
        return Response(status_code=status.HTTP_200_OK)

    latest_thread = customer_threads[-1]
    thread_id = latest_thread.get("id")
    text_to_translate = _extract_thread_body(latest_thread)

    if not text_to_translate:
        logger.info("Latest customer thread has no body for conversation %s", conversation_id)
        return Response(status_code=status.HTTP_200_OK)

    # If already English, stop: no translation, no note
    if translation_service.detect_language(text_to_translate) == "en":
        logger.info(text_to_translate)
        logger.info("Webhook: thread content is English; skipping translation and note for conversation %s", conversation_id)
        # return Response(status_code=status.HTTP_200_OK)

    try:
        translation = await translation_service.translate_to_english(text_to_translate)
    except Exception as e:
        logger.exception("Translation failed for conversation %s thread %s: %s", conversation_id, thread_id, e)
        return Response(status_code=status.HTTP_200_OK)

    # Only add note when translation is non-empty (empty = already English or AI returned empty)
    if translation:
        note_body = f"---\nTranslation to English\n---\n\n{translation}"
        try:
            await helpscout_service.create_note(conversation_id, note_body)
            logger.info("Translation note saved for conversation %s (thread %s)", conversation_id, thread_id)
        except Exception as e:
            logger.warning("Failed to save translation note for conversation %s: %s", conversation_id, e)

    return Response(status_code=status.HTTP_200_OK)
