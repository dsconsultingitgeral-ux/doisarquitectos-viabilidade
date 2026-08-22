import streamlit as st

DEFAULTS = {
    "step": 1,
    "location": "",
    "municipality": "",
    "parish": "",
    "locality": "",
    "article": "",
    "known_area": "",
    "location_confirmed": False,
    "uploaded_files": [],
    "analysis_text": "",
    "analysis_sources": [],
    "response_id": "",
}

def init_state():
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def go(step: int):
    st.session_state.step = max(1, min(4, int(step)))
    st.rerun()
