from __future__ import annotations
import streamlit as st

def _secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

GEMINI_API_KEY = _secret("GEMINI_API_KEY", "")
APP_USER = _secret("APP_USER", "admin1")
APP_PASSWORD = _secret("APP_PASSWORD", "doisarquitetos")
GEMINI_MODEL = _secret("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODELS = [x.strip() for x in str(_secret("GEMINI_FALLBACK_MODELS", "gemini-3.7-flash")).split(",") if x.strip()]
GEMINI_TIMEOUT_MS = int(_secret("GEMINI_TIMEOUT_MS", 45000))
