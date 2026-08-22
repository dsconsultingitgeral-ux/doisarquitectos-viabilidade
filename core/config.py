import os
import streamlit as st


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

GEMINI_API_KEY = _secret("GEMINI_API_KEY", "")
APP_USER = _secret("APP_USER", "admin1")
APP_PASSWORD = _secret("APP_PASSWORD", "doisarquitetos")

# Modelo de produção recomendado. Se um endpoint estiver congestionado, o serviço
# faz fallback automaticamente para outros modelos estáveis.
GEMINI_MODEL = _secret("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in str(_secret("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-3.5-flash,gemini-3.7-flash")).split(",") if m.strip()
]
GEMINI_TIMEOUT_MS = int(_secret("GEMINI_TIMEOUT_MS", 45000))

OFFICIAL_SOURCE_DOMAINS = [
    "diariodarepublica.pt", "dre.pt", "dgterritorio.gov.pt", "snit-sgt.dgterritorio.gov.pt",
    "ccdr.pt", "apambiente.pt", "icnf.pt", "patrimoniocultural.gov.pt",
]
