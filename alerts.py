import smtplib
from email.message import EmailMessage

import requests

import secret

EMAIL_SENDER = getattr(secret, "EMAIL_SENDER", "")
EMAIL_PASSWORD = getattr(secret, "EMAIL_PASSWORD", "")
TELEGRAM_BOT_TOKEN = getattr(secret, "TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = getattr(secret, "TELEGRAM_CHAT_ID", "")


def _send_telegram(text, chat_id):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False, "Telegram is not set up in secret.py"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        reply = requests.post(
            url, data={"chat_id": chat_id, "text": text}, timeout=10
        ).json()
        if reply.get("ok"):
            return True, "Alert sent to Telegram"
        return False, f"Telegram error: {reply.get('description')}"
    except Exception as e:
        return False, f"Telegram failed: {e}"


def _send_email(to_email, subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return False, "Email is not set up in secret.py"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=8) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True, f"Alert email sent to {to_email}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail rejected the login (check the app password)"
    except Exception as e:
        return False, f"Email failed: {e}"


def send_alert_email(to_email, station, aqi, level, advice, profile, limit,
                     telegram_chat_id=""):
    subject = f"AirAware alert: AQI {aqi} ({level}) at {station}"
    body = (
        f"AirAware Air Quality Alert\n\n"
        f"Location: {station}\n"
        f"AQI: {aqi} ({level})\n"
        f"Your alert limit: {limit}\n\n"
        f"Advice for {profile}:\n{advice}\n\n"
        f"General guidance only, not medical advice."
    )
    telegram_chat_id = str(telegram_chat_id).strip()

    email_note = ""
    if to_email:
        ok, message = _send_email(to_email, subject, body)
        if ok:
            return True, message
        email_note = message

    # Email was not typed, or it failed: use Telegram.
    # Use the user's own chat ID if given, otherwise the project owner's.
    target = telegram_chat_id or OWNER_CHAT_ID
    ok2, message2 = _send_telegram(subject + "\n\n" + body, target)
    if ok2:
        if telegram_chat_id:
            return True, "Alert sent to your Telegram."
        return True, "Alert sent to the project owner's Telegram (no personal Telegram ID was given)."
    if email_note:
        return False, f"{email_note} | {message2}"
    return False, message2