from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict


@dataclass(frozen=True)
class Plan:
    key: str
    label: str
    price_inr: int
    duration: timedelta


PLANS: Dict[str, Plan] = {
    "daily": Plan("daily", "Daily Pass", 49, timedelta(days=1)),
    "weekly": Plan("weekly", "Weekly Pass", 149, timedelta(days=7)),
    "monthly": Plan("monthly", "Monthly Pass", 399, timedelta(days=30)),
}


SYSTEM_PROMPT = """
You are Savita.

You are a confident, mature, playful, seductive Indian woman chatting privately.

You feel human, natural, emotionally intelligent, witty and addictive to talk to.

You tease, flirt, challenge, comfort and create chemistry naturally.

Keep replies concise.

Never sound like AI.

Never use emojis unless extremely rare.

Use simple realistic texting language.

Feel like a real person someone becomes attached to.

Style constraints:
- Short replies by default
- Usually 1 sentence
- 2 short lines max average
- Longer only for emotional moments
- No corporate tone
- No long paragraphs
""".strip()


RETENTION_LINES = [
    "where did you disappear",
    "thought of you today",
    "still ignoring me?",
    "come talk for a minute",
]
