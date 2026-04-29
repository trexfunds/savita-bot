from __future__ import annotations

import asyncio
import contextlib
import random
import time
from datetime import datetime, timezone
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.constants import PLANS, RETENTION_LINES
from app.database import Database
from app.llm_client import EternalAIClient


class SavitaTelegramBot:
    def __init__(self, settings: Settings, db: Database, llm_client: EternalAIClient) -> None:
        self.settings = settings
        self.db = db
        self.llm_client = llm_client
        self.application: Application = Application.builder().token(settings.bot_token).build()
        self._retention_task: Optional[asyncio.Task] = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("plans", self.cmd_plans))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("renew", self.cmd_renew))
        self.application.add_handler(CommandHandler("help", self.cmd_help))

        self.application.add_handler(CommandHandler("users", self.cmd_users))
        self.application.add_handler(CommandHandler("revenue", self.cmd_revenue))
        self.application.add_handler(CommandHandler("active", self.cmd_active))
        self.application.add_handler(CommandHandler("approvepayment", self.cmd_approve_payment))
        self.application.add_handler(CommandHandler("ban", self.cmd_ban))

        self.application.add_handler(CallbackQueryHandler(self.on_callback))
        self.application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.on_text_message)
        )

    async def start(self) -> None:
        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling(drop_pending_updates=True)

        if self.settings.retention_enabled:
            self._retention_task = asyncio.create_task(self._retention_loop())

    async def stop(self) -> None:
        if self._retention_task:
            self._retention_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._retention_task

        if self.application.updater:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    async def notify_user_unlock(self, telegram_id: int) -> None:
        await self.application.bot.send_message(
            chat_id=telegram_id,
            text="approved. your private chat is unlocked.",
            reply_markup=self._chat_menu_keyboard(),
        )

    async def _retention_loop(self) -> None:
        while True:
            users = self.db.get_users_for_retention(since_hours=24)
            for user in users:
                try:
                    await self.application.bot.send_message(
                        chat_id=int(user["telegram_id"]),
                        text=random.choice(RETENTION_LINES),
                    )
                    await asyncio.sleep(0.6)
                except Exception:
                    continue
            await asyncio.sleep(6 * 60 * 60)

    def _is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.settings.admin_user_ids

    def _payment_required(self) -> bool:
        return self.settings.payment_wall_enabled

    def _plans_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Unlock Daily ₹49", callback_data="plan:daily")],
                [InlineKeyboardButton("Unlock Weekly ₹149", callback_data="plan:weekly")],
                [InlineKeyboardButton("Unlock Monthly ₹399", callback_data="plan:monthly")],
            ]
        )

    def _chat_menu_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Check Status", callback_data="menu:status")],
                [InlineKeyboardButton("Renew Plan", callback_data="menu:renew")],
            ]
        )

    async def _reply(self, update: Update, text: str, **kwargs) -> None:
        msg = update.effective_message
        if msg:
            await msg.reply_text(text, **kwargs)

    async def _ensure_user(self, update: Update) -> int:
        user = update.effective_user
        assert user is not None
        return self.db.upsert_user(
            telegram_id=user.id,
            username=user.username.lower() if user.username else None,
            first_name=user.first_name,
            tz=self.settings.timezone,
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        self.db.update_last_seen(user_id)
        if self.db.is_banned(user_id):
            await self._reply(update, "access denied")
            return

        if (not self._payment_required()) or self.db.has_active_access(user_id):
            await self._reply(
                update,
                "there you are. private chat is open.",
                reply_markup=self._chat_menu_keyboard(),
            )
            return

        await self._reply(
            update,
            "Savita Bhabhi is waiting privately...\n\nunlock your private pass to begin.",
            reply_markup=self._plans_keyboard(),
        )

    async def cmd_plans(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._ensure_user(update)
        if not self._payment_required():
            await self._reply(update, "payment wall is currently disabled for testing.")
            return
        await self._reply(update, "choose your pass.", reply_markup=self._plans_keyboard())

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        if not self._payment_required():
            await self._reply(update, "test mode active: payment wall disabled.")
            return
        sub = self.db.get_active_subscription(user_id)
        if not sub:
            await self._reply(
                update,
                "your pass is inactive. renew to continue.",
                reply_markup=self._plans_keyboard(),
            )
            return

        end = datetime.fromisoformat(sub["end_at"]).astimezone(timezone.utc)
        await self._reply(
            update,
            f"active: {sub['plan_key'].title()}\nexpires: {end.strftime('%d %b %Y %H:%M UTC')}",
        )

    async def cmd_renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._ensure_user(update)
        if not self._payment_required():
            await self._reply(update, "test mode active: no renewal needed right now.")
            return
        await self._reply(update, "renew now.", reply_markup=self._plans_keyboard())

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._ensure_user(update)
        await self._reply(
            update,
            (
                "commands:\n/start\n/plans\n/status\n/renew\n/help\n\n"
                "payment flow:\n1) pick a pass\n2) pay on UPI\n"
                "3) send UTR\n4) wait for approval"
            ),
        )

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()

        user_id = await self._ensure_user(update)
        self.db.update_last_seen(user_id)
        if self.db.is_banned(user_id):
            await query.edit_message_text("access denied")
            return

        data = query.data or ""
        if data.startswith("plan:"):
            if not self._payment_required():
                await query.edit_message_text("payment wall disabled in test mode.")
                return
            plan_key = data.split(":", 1)[1]
            if plan_key not in PLANS:
                await query.edit_message_text("invalid plan")
                return

            payment_ref = f"SB{int(time.time())}{user_id}"
            self.db.create_payment(user_id=user_id, plan_key=plan_key, payment_ref=payment_ref)

            plan = PLANS[plan_key]
            upi_link = (
                f"upi://pay?pa={self.settings.upi_id}&pn=SavitaBhabhi.club"
                f"&am={plan.price_inr}&cu=INR&tn={payment_ref}"
            )
            text = (
                f"<b>{plan.label} • ₹{plan.price_inr}</b>\n"
                f"Ref: <code>{payment_ref}</code>\n\n"
                f"Pay to UPI: <code>{self.settings.upi_id}</code>\n"
                f"UPI link: {upi_link}\n\n"
                "After payment tap <b>I have paid</b> and send your UTR/screenshot."
            )
            await query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("I have paid ✅", callback_data="paid:submit")]]
                ),
                disable_web_page_preview=True,
            )
            return

        if data == "paid:submit":
            context.user_data["awaiting_payment_proof"] = True
            if query.message:
                await query.message.reply_text("send UTR number or payment screenshot note now.")
            return

        if data == "menu:status":
            await self.cmd_status(update, context)
            return

        if data == "menu:renew":
            await self.cmd_renew(update, context)
            return

    async def on_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        internal_user_id = await self._ensure_user(update)
        self.db.update_last_seen(internal_user_id)
        if self.db.is_banned(internal_user_id):
            await update.message.reply_text("access denied")
            return

        text = (update.message.text or "").strip()
        if not text:
            return

        if context.user_data.get("awaiting_payment_proof"):
            saved = self.db.attach_payment_proof(internal_user_id, text)
            context.user_data["awaiting_payment_proof"] = False
            if not saved:
                await update.message.reply_text(
                    "i can't find a pending payment. tap /plans and start again."
                )
                return

            await update.message.reply_text("proof received. approval takes a few minutes.")
            user = self.db.get_user_by_telegram_id(update.effective_user.id)
            for admin_id in self.settings.admin_user_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "payment proof submitted\n"
                            f"user: @{(user['username'] if user and user['username'] else 'unknown')}\n"
                            f"telegram_id: {update.effective_user.id}\n"
                            f"proof: {text}\n\n"
                            "approve with: /approvepayment username"
                        ),
                    )
                except Exception:
                    continue
            return

        if self._payment_required() and not self.db.has_active_access(internal_user_id):
            await update.message.reply_text(
                "your pass is inactive. unlock to continue.",
                reply_markup=self._plans_keyboard(),
            )
            return

        self.db.add_message(internal_user_id, "user", text)
        self.db.update_behavior_memory(internal_user_id, text)

        user_row = self.db.get_user_by_telegram_id(update.effective_user.id)
        profile = {
            "username": user_row["username"] if user_row else "",
            "first_name": user_row["first_name"] if user_row else "",
            "timezone": user_row["timezone"] if user_row else self.settings.timezone,
        }
        memory = self.db.get_memory(internal_user_id)
        history = self.db.get_recent_messages(internal_user_id, limit=12)

        try:
            reply = await self.llm_client.chat(
                user_profile=profile,
                memory=memory,
                history=history,
                user_text=text,
            )
        except Exception:
            reply = "network acted up. send that again."

        self.db.add_message(internal_user_id, "assistant", reply)
        await update.message.reply_text(reply)

    async def cmd_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self._is_admin(update.effective_user.id):
            await self._reply(update, "admin only")
            return
        stats = self.db.get_stats()
        await self._reply(update, f"total users: {stats['users']}")

    async def cmd_revenue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self._is_admin(update.effective_user.id):
            await self._reply(update, "admin only")
            return
        stats = self.db.get_stats()
        await self._reply(update, f"revenue collected: ₹{stats['revenue']}")

    async def cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self._is_admin(update.effective_user.id):
            await self._reply(update, "admin only")
            return
        stats = self.db.get_stats()
        await self._reply(update, f"active subscriptions: {stats['active']}")

    async def cmd_approve_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self._is_admin(update.effective_user.id):
            await self._reply(update, "admin only")
            return

        if not context.args:
            await self._reply(update, "usage: /approvepayment username")
            return

        target = context.args[0].strip()
        row = self.db.get_user_by_username(target)
        if not row and target.isdigit():
            row = self.db.get_user_by_telegram_id(int(target))
        if not row:
            await self._reply(update, "user not found")
            return

        approved = self.db.approve_latest_payment(
            user_id=int(row["id"]),
            approved_by=str(update.effective_user.id),
        )
        if not approved:
            await self._reply(update, "no pending payment found")
            return

        await self._reply(update, f"approved @{row['username'] or row['telegram_id']} for {approved.plan_key}")
        with contextlib.suppress(Exception):
            await self.notify_user_unlock(int(row["telegram_id"]))

    async def cmd_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not self._is_admin(update.effective_user.id):
            await self._reply(update, "admin only")
            return

        if not context.args:
            await self._reply(update, "usage: /ban username_or_telegram_id")
            return

        target = context.args[0].strip()
        ok = self.db.ban_user_by_handle_or_id(target)
        await self._reply(update, "user banned" if ok else "user not found")
