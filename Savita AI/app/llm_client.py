from __future__ import annotations

from typing import Dict, List

import httpx

from app.config import Settings
from app.constants import SYSTEM_PROMPT


class EternalAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(
        self,
        user_profile: Dict[str, str],
        memory: Dict[str, str],
        history: List[Dict[str, str]],
        user_text: str,
    ) -> str:
        memory_bits = [
            f"Name: {user_profile.get('first_name') or 'Unknown'}",
            f"Username: @{user_profile.get('username') or 'unknown'}",
            f"Timezone: {user_profile.get('timezone') or 'Unknown'}",
            f"Tone level: {memory.get('tone_level', 'balanced')}",
            f"Favorite topics: {memory.get('favorite_topics', 'unknown')}",
            f"Emotional notes: {memory.get('emotional_notes', 'none')}",
            f"Last seen: {memory.get('last_seen', 'unknown')}",
        ]
        profile_context = "\n".join(memory_bits)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "User memory context for realistic continuity:\n"
                    f"{profile_context}\n"
                    "Keep responses concise and natural."
                ),
            },
        ]
        messages.extend(history[-12:])
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.settings.eternal_model,
            "messages": messages,
            "temperature": 0.95,
            "max_completion_tokens": 140,
            "stream": False,
        }

        headers = {
            "x-api-key": self.settings.eternal_api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                self.settings.eternal_api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            return "you got quiet on me... say that again"

        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            return "hmm... tell me that one more time"
        return content
