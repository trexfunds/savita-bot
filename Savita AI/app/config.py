from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _parse_admin_ids(raw: str) -> List[int]:
    if not raw.strip():
        return []
    ids: List[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        ids.append(int(item))
    return ids


@dataclass(frozen=True)
class Settings:
    bot_token: str
    eternal_api_key: str
    eternal_api_url: str
    upi_id: str
    port: int
    admin_user_ids: List[int]
    timezone: str
    retention_enabled: bool
    payment_wall_enabled: bool
    eternal_model: str
    database_path: str
    callback_secret: str


def get_settings() -> Settings:
    retention_value = os.getenv("RETENTION_ENABLED", "false").strip().lower()
    payment_wall_value = os.getenv("PAYMENT_WALL_ENABLED", "true").strip().lower()
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        eternal_api_key=os.getenv("ETERNAL_API_KEY", "").strip(),
        eternal_api_url=os.getenv(
            "ETERNAL_API_URL", "https://open.eternalai.org/v1/chat/completions"
        ).strip(),
        upi_id=os.getenv("UPI_ID", "").strip(),
        port=int(os.getenv("PORT", "8000")),
        admin_user_ids=_parse_admin_ids(os.getenv("ADMIN_USER_IDS", "")),
        timezone=os.getenv("TIMEZONE", "Asia/Kolkata").strip(),
        retention_enabled=retention_value in {"1", "true", "yes", "on"},
        payment_wall_enabled=payment_wall_value in {"1", "true", "yes", "on"},
        eternal_model=os.getenv("ETERNAL_MODEL", "uncensored-eternal-ai-1.0").strip(),
        database_path=os.getenv("DATABASE_PATH", "savita.db").strip(),
        callback_secret=os.getenv("CALLBACK_SECRET", "").strip(),
    )
