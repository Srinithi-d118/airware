import smtplib
from email.message import EmailMessage
from secret import EMAIL_SENDER, EMAIL_PASSWORD


def send_alert_email(to_email, station, aqi, level, advice, profile, limit):
    msg = EmailMessage()
    msg["Subject"] = f"AirAware alert: AQI {aqi} ({level}) at {station}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    msg.set_content(
        f"AirAware Air Quality Alert\n\n"
        f"Location: {station}\n"
        f"AQI: {aqi} ({level})\n"
        f"Your alert limit: {limit}\n\n"
        f"Advice for {profile}:\n{advice}\n\n"
        f"General guidance only, not medical advice."
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True, f"Alert email sent to {to_email}"
    except Exception as e:
        return False, f"Could not send email: {e}"