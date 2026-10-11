import requests
import secret

TO_EMAIL = "dhandapanik284@gmail.com" 

reply = requests.post(
    "https://api.brevo.com/v3/smtp/email",
    headers={
        "api-key": secret.BREVO_API_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    },
    json={
        "sender": {"name": "AirAware", "email": secret.EMAIL_SENDER},
        "to": [{"email": TO_EMAIL}],
        "subject": "AirAware test",
        "textContent": "This is a test email from AirAware.",
    },
    timeout=15,
)
print("Status:", reply.status_code)
print("Reply:", reply.text)