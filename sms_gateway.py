from __future__ import annotations

import re


def normalize_kenyan_phone(value: str) -> str | None:
    """Normalize common Kenyan mobile formats to the +254 international format."""
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9 and digits[0] in ("1", "7"):
        digits = "254" + digits
    if len(digits) == 12 and digits.startswith("254") and digits[3] in ("1", "7"):
        return "+" + digits
    return None


def send_africas_talking_sms(username: str, api_key: str, sender_id: str,
                             message: str, recipients: list[str]):
    """Submit one meeting SMS campaign through the official Africa's Talking SDK."""
    import africastalking

    africastalking.initialize(username, api_key)
    return africastalking.SMS.send(
        message,
        recipients,
        sender_id=sender_id,
        enqueue=True,
    )
