"""Handler for convo.agent.reply.created: evaluate agent reply (same logic as POST /reply/agent)."""

import logging
from typing import Any, Dict

from app.routes.reply import run_agent_evaluation

logger = logging.getLogger(__name__)


async def handle_agent_reply_created(payload: Dict[str, Any]) -> None:
    """
    Handle convo.agent.reply.created: evaluate the latest agent reply using the
    same logic as POST /reply/agent and optionally add a note when average_score < 6.
    """
    conversation_id = payload.get("id")
    if conversation_id is None:
        logger.warning("Webhook payload missing conversation id")
        return
    conversation_id = str(conversation_id)
    embedded = payload.get("_embedded") or {}
    threads = embedded.get("threads") or []
    agent_threads = [t for t in reversed(threads) if t.get("type") == "message"]
    if not agent_threads:
        logger.info(
            "No agent reply thread in webhook for conversation %s", conversation_id
        )
        return
    latest_agent_thread = agent_threads[-1]
    thread_id = latest_agent_thread.get("id")
    if thread_id is None:
        logger.warning(
            "Agent reply thread missing id for conversation %s", conversation_id
        )
        return
    thread_id_str = str(thread_id)
    try:
        await run_agent_evaluation(conversation_id, thread_id_str)
        logger.info(
            "Agent reply evaluation completed for conversation %s thread %s",
            conversation_id,
            thread_id_str,
        )
    except Exception as e:
        logger.exception(
            "Agent reply evaluation failed for conversation %s thread %s: %s",
            conversation_id,
            thread_id_str,
            e,
        )
