from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.bot_service import SavitaTelegramBot
from app.config import get_settings
from app.database import Database
from app.llm_client import EternalAIClient


settings = get_settings()
db = Database(settings.database_path)
llm_client = EternalAIClient(settings)
bot = SavitaTelegramBot(settings=settings, db=db, llm_client=llm_client)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    await bot.start()
    try:
        yield
    finally:
        await bot.stop()


app = FastAPI(title="SavitaBhabhi.club", version="1.0.0", lifespan=lifespan)


class UpiCallbackPayload(BaseModel):
    payment_ref: str
    status: str
    source: Optional[str] = "upi"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "SavitaBhabhi.club"}


@app.post("/payments/callback")
async def payment_callback(
    payload: UpiCallbackPayload,
    x_admin_secret: Optional[str] = Header(default=None),
) -> dict:
    """
    UPI/manual callback endpoint.
    Keep this endpoint token-protected via reverse proxy or custom header in production.
    """
    if settings.callback_secret and x_admin_secret != settings.callback_secret:
        raise HTTPException(status_code=401, detail="Invalid callback secret")

    if payload.status.lower() not in {"success", "approved"}:
        return {"ok": True, "message": "ignored non-success status"}

    user_id = db.approve_by_payment_ref(payload.payment_ref, approved_by="callback")
    if not user_id:
        return {"ok": True, "message": "no matching pending payment"}

    user_row = db.get_user_by_id(user_id)
    if user_row:
        try:
            await bot.notify_user_unlock(int(user_row["telegram_id"]))
        except Exception:
            pass
    return {"ok": True, "message": "subscription activated"}
