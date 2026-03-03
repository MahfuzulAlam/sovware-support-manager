"""
Help Scout webhook event handler registry.

To add a new event:
  1. Create a new module in this package (e.g. my_event.py).
  2. Implement an async handler: async def handle_my_event(payload: Dict[str, Any]) -> None.
  3. Register it in EVENT_HANDLERS below with the Help Scout event name as key.

The webhook route will dispatch by X-HelpScout-Event; unknown events are logged and ignored.
"""

from typing import Any, Callable, Dict, Optional

from app.routes.webhook_handlers.agent_reply import handle_agent_reply_created
from app.routes.webhook_handlers.customer_reply import handle_customer_reply_created

# Type for async handlers that receive the webhook payload
WebhookEventHandler = Callable[[Dict[str, Any]], Any]

# Registry: Help Scout event name -> async handler(payload)
EVENT_HANDLERS: Dict[str, WebhookEventHandler] = {
    "convo.customer.reply.created": handle_customer_reply_created,
    "convo.agent.reply.created": handle_agent_reply_created,
}


def get_handler(event: str) -> Optional[WebhookEventHandler]:
    """Return the registered handler for the given event, or None if unknown."""
    return EVENT_HANDLERS.get(event)


def register_handler(event: str, handler: WebhookEventHandler) -> None:
    """Register a handler for an event (e.g. for plugins or tests)."""
    EVENT_HANDLERS[event] = handler
