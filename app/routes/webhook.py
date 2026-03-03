"""Help Scout webhook endpoint: signature verification and event dispatch via registry."""

import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request, Response, status

from app.config import settings
from app.routes.webhook_handlers import get_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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
    description="Receives Help Scout webhook events. Dispatches by X-HelpScout-Event "
    "using a registry; add new events by registering handlers in webhook_handlers.",
)
async def helpscout_webhook(request: Request) -> Response:
    """
    Handle Help Scout webhooks.

    - Verifies X-HelpScout-Signature when HELPSCOUT_WEBHOOK_SECRET is set.
    - Dispatches to the handler registered for the event (see webhook_handlers package).
    - Unknown events are logged and acknowledged with 200.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-HelpScout-Signature") or request.headers.get(
        "x-helpscout-signature"
    )
    event = request.headers.get("X-HelpScout-Event") or request.headers.get(
        "x-helpscout-event"
    )

    secret = settings.helpscout_webhook_secret
    if secret:
        if not signature:
            logger.warning("Help Scout webhook missing X-HelpScout-Signature header")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)
        if not _verify_helpscout_signature(body_bytes, signature, secret):
            logger.warning("Help Scout webhook signature verification failed")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    else:
        logger.debug(
            "HELPSCOUT_WEBHOOK_SECRET not set; skipping signature verification"
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("Invalid webhook body: %s", e)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    handler = get_handler(event or "")
    if handler:
        try:
            await handler(payload)
        except Exception as e:
            logger.exception("Webhook handler failed for event %s: %s", event, e)
    else:
        logger.info("Ignoring unregistered Help Scout event: %s", event)

    return Response(status_code=status.HTTP_200_OK)
