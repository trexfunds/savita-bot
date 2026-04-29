# SavitaBhabhi.club Telegram Bot

Production-oriented paid Telegram chatbot business backend built with **FastAPI + python-telegram-bot + SQLite**.

## Features

- Paid-first Telegram flow (no free chat)
- Plans:
  - Daily ₹49 (1 day)
  - Weekly ₹149 (7 days)
  - Monthly ₹399 (30 days)
- UPI payment instructions with unique payment reference
- Manual payment proof + admin approval flow
- Callback-ready payment endpoint for UPI/Razorpay-style integrations
- Subscription expiry enforcement before every chat message
- EternalAI uncensored chat API integration
- Memory system (tone, emotional notes, topics, last seen)
- Admin commands:
  - `/users`
  - `/revenue`
  - `/active`
  - `/approvepayment username`
  - `/ban username_or_telegram_id`
- Optional retention nudges for active users

## Project Structure

```text
app/
  __init__.py
  bot_service.py
  config.py
  constants.py
  database.py
  llm_client.py
  main.py
.env.example
requirements.txt
```

## Setup

1. Create virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
```

Fill `.env`:

```env
BOT_TOKEN=
ETERNAL_API_KEY=
ETERNAL_API_URL=https://api.eternalai.org/v1/chat/completions
ETERNAL_MODEL=uncensored-chat
UPI_ID=yourupi@bank
PORT=8000
ADMIN_USER_IDS=123456789,987654321
TIMEZONE=Asia/Kolkata
RETENTION_ENABLED=false
DATABASE_PATH=savita.db
CALLBACK_SECRET=strong-secret-value
```

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The app starts:
- FastAPI server on `PORT`
- Telegram bot polling in the same process

## Telegram User Flow

1. User sends `/start`
2. Bot shows premium plan buttons
3. User selects plan and pays via UPI
4. User taps **I have paid** and submits UTR/screenshot text
5. Admin approves with `/approvepayment username`
6. Access unlocks instantly

## Core Commands (User)

- `/start`
- `/plans`
- `/status`
- `/renew`
- `/help`

## Admin Operations

- `/users` → total users
- `/revenue` → total approved revenue
- `/active` → active subscriptions
- `/approvepayment username` → approves latest pending payment
- `/ban username_or_telegram_id` → blocks access

## Payment Callback API (for future gateways)

Endpoint:

`POST /payments/callback`

Headers:

- `x-admin-secret: <CALLBACK_SECRET>` (required if configured)

Body:

```json
{
  "payment_ref": "SB1714220000123",
  "status": "success",
  "source": "upi"
}
```

This marks matching pending payment as approved and activates subscription.

## Deployment Notes

- Put behind reverse proxy (Nginx/Caddy)
- Keep `.env` secret
- Use strong `CALLBACK_SECRET`
- Restrict callback endpoint by IP at proxy layer if possible
- Back up `DATABASE_PATH` regularly
- For scale, move from SQLite to Postgres later

## Razorpay Upgrade Path

Current architecture is ready for Razorpay:

- Keep plans/subscription logic unchanged
- Replace or extend payment creation with Razorpay order creation
- Verify Razorpay webhook signature in `/payments/callback`
- Reuse `approve_by_payment_ref(...)` subscription activation logic
