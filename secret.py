import os

try:
    import secret_local as _local
except Exception:
    _local = None


def _from_streamlit(name):
    """Read a value from Streamlit's cloud secrets, if they exist."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return None


def _get(name, default=""):
    value = _from_streamlit(name)
    if value:
        return value
    if os.environ.get(name):
        return os.environ[name]
    if _local is not None and hasattr(_local, name):
        return getattr(_local, name)
    return default


TOKEN = _get("TOKEN")
EMAIL_SENDER = _get("EMAIL_SENDER")
EMAIL_PASSWORD = _get("EMAIL_PASSWORD")
BREVO_API_KEY = _get("BREVO_API_KEY")
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")