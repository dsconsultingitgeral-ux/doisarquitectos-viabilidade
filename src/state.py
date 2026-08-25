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
    "geo_lat": None,
    "geo_lon": None,
    "geo_display_name": "",
    "geo_source_url": "",
    "geo_precision": "",
    "parcel_polygon_geojson": None,
    "parcel_polygon_coords": [],
    "uploaded_files": [],
    "analysis_text": "",
    "analysis_summary": {},
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
