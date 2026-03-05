# owner_guard.py
"""
Centralized message-ownership tracking for user-specific inline buttons.

When a game sends a message with inline buttons, it registers the sender
as the owner via `set_owner()`.  Every callback handler then calls
`check_owner()` before processing – if the clicker is not the owner,
an alert is shown and the handler returns early without touching the message.

This works for both private chats and group chats.
"""

from __future__ import annotations
from typing import Optional

# Maps (chat_id, message_id) -> owner_user_id
_owners: dict[tuple[int, int], int] = {}


def set_owner(chat_id: int, message_id: int, user_id: int) -> None:
    """Register `user_id` as the owner of a specific message."""
    _owners[(chat_id, message_id)] = user_id


def get_owner(chat_id: int, message_id: int) -> Optional[int]:
    """Return the owner user_id for a message, or None if not tracked."""
    return _owners.get((chat_id, message_id))


def remove_owner(chat_id: int, message_id: int) -> None:
    """Remove ownership record when a game ends."""
    _owners.pop((chat_id, message_id), None)


async def check_owner(query, alert_text: str = "❌ This is not your game!") -> bool:
    """
    Check whether the callback query sender is the message owner.

    Returns True if the user IS the owner (or no owner is registered).
    Returns False and shows an alert if the user is NOT the owner.

    Usage inside a callback handler:
        if not await check_owner(update.callback_query):
            return
    """
    chat_id = query.message.chat_id
    msg_id = query.message.message_id
    user_id = query.from_user.id

    owner = _owners.get((chat_id, msg_id))
    if owner is not None and owner != user_id:
        await query.answer(alert_text, show_alert=True)
        return False
    return True
