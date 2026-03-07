"""Handlers for convo.created and convo.customer.reply.created: evaluate + translate customer message."""

import logging
from typing import Any, Dict

from app.orchestrator.reply import run_customer_reply_evaluation
from app.orchestrator.webhook_handlers.utils import extract_thread_body
from app.services.helpscout_service import helpscout_service
from app.sub_agents.translator import translation_service

logger = logging.getLogger(__name__)


async def handle_convo_created(payload: Dict[str, Any]) -> None:
    """
    Handle convo.created: run the same flow as customer reply (evaluate + translate
    the initial customer message).
    """
    await handle_customer_reply_created(payload)


async def handle_customer_reply_created(payload: Dict[str, Any]) -> None:
    """
    Handle convo.customer.reply.created: run customer behavior evaluation on the latest
    customer thread, then translate it to English and add as a note when not already English.
    """
    conversation_id = payload.get("id")
    if conversation_id is None:
        logger.warning("Webhook payload missing conversation id")
        return
    conversation_id = str(conversation_id)
    embedded = payload.get("_embedded") or {}
    threads = embedded.get("threads") or []
    customer_threads = [t for t in reversed(threads) if t.get("type") == "customer"]
    if not customer_threads:
        logger.info("No customer thread in webhook for conversation %s", conversation_id)
        return
    latest_thread = customer_threads[-1]
    thread_id = latest_thread.get("id")
    text_to_translate = extract_thread_body(latest_thread)

    # Execute the customer reply evaluation
    if text_to_translate:
        try:
            await run_customer_reply_evaluation(conversation_id, thread_id)
            logger.info(
                "Customer reply evaluation completed for conversation %s thread %s",
                conversation_id,
                thread_id,
            )
        except Exception as e:
            logger.exception(
                "Customer reply evaluation failed for conversation %s thread %s: %s",
                conversation_id,
                thread_id,
                e,
            )

    # Skip translation if the thread is already in English
    if not text_to_translate:
        logger.info(
            "Latest customer thread has no body for conversation %s", conversation_id
        )
        return
    if translation_service.detect_language(text_to_translate) == "en":
        logger.info(
            "Webhook: thread content is English; skipping translation for conversation %s",
            conversation_id,
        )
        return
    try:
        translation = await translation_service.translate_to_english(text_to_translate)
    except Exception as e:
        logger.exception(
            "Translation failed for conversation %s thread %s: %s",
            conversation_id,
            thread_id,
            e,
        )
        return
    if translation:
        note_body = f"---\nTranslation to English\n---\n\n{translation}"
        try:
            await helpscout_service.create_note(conversation_id, note_body)
            logger.info(
                "Translation note saved for conversation %s (thread %s)",
                conversation_id,
                thread_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to save translation note for conversation %s: %s",
                conversation_id,
                e,
            )
