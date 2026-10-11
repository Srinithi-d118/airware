from alerts import send_alert_email

ok, message = send_alert_email(
    "PUT_YOUR_EMAIL_HERE",
    "Test Station",
    150,
    "Unhealthy for sensitive groups",
    "This is a test email from AirAware.",
    "Healthy adult",
    100,
)
print(ok, message)