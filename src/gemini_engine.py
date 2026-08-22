from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any
from pathlib import Path
import os
import tempfile
import time

from google import genai
from google.genai import types


@dataclass
class SourceLink:
    index: int
    title: str
    url: str


def _secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return str(os.getenv(name, default) or default)


def get_client() -> genai.Client:
    key = _secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada. "
            "Define-a apenas nos Secrets privados do Streamlit."
        )
    return genai.Client(api_key=key)


def get_model() -> str:
    # Current Google AI documentation examples use Gemini 3.7 Flash.
    # The cabinet can change this privately in Streamlit Secrets without
    # changing the GitHub repository.
    return _secret("GEMINI_MODEL", "gemini-3.7-flash")


def _wait_until_ready(client: genai.Client, uploaded, timeout_seconds: int = 90):
    """Wait defensively when the Gemini Files API exposes a processing state."""
    started = time.time()
    current = uploaded

    while time.time() - started < timeout_seconds:
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", None) if state is not None else None

        if not state_name or state_name.upper() in {"ACTIVE", "READY", "SUCCEEDED"}:
            return current

        if state_name.upper() in {"FAILED", "ERROR"}:
            raise RuntimeError(f"O Gemini não conseguiu processar o ficheiro {getattr(current, 'name', '')}.")

        time.sleep(2)
        try:
            current = client.files.get(name=current.name)
        except Exception:
            # Some file types can be usable immediately even if state polling
            # is not exposed consistently.
            return current

    return current


def upload_files(files: Iterable[Any]) -> list[Any]:
    """Upload Streamlit files to Gemini Files API.

    Gemini temporarily stores uploaded files. The app creates a temporary
    local copy only for the duration of the upload and deletes it immediately.
    """
    client = get_client()
    uploaded_files = []

    for f in files:
        suffix = Path(f.name).suffix or ".bin"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(f.getvalue())
                temp_path = tmp.name

            uploaded = client.files.upload(file=temp_path)
            uploaded = _wait_until_ready(client, uploaded)
            uploaded_files.append(uploaded)
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    return uploaded_files


def _extract_grounding_sources(response) -> list[SourceLink]:
    """Extract web sources returned by Gemini Google Search grounding."""
    found: list[SourceLink] = []
    seen: set[str] = set()

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return found

    metadata = getattr(candidates[0], "grounding_metadata", None)
    if not metadata:
        return found

    chunks = getattr(metadata, "grounding_chunks", None) or []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if not web:
            continue

        url = getattr(web, "uri", None) or getattr(web, "url", None)
        title = getattr(web, "title", None) or "Fonte consultada"

        if url and url not in seen:
            seen.add(url)
            found.append(SourceLink(
                index=len(found) + 1,
                title=str(title),
                url=str(url),
            ))

    return found


def run_full_analysis(prompt: str, uploaded_files: Iterable[Any]):
    client = get_client()
    gemini_files = upload_files(uploaded_files)

    contents: list[Any] = [prompt]
    contents.extend(gemini_files)

    google_search = types.Tool(
        google_search=types.GoogleSearch()
    )

    config = types.GenerateContentConfig(
        tools=[google_search],
        temperature=0.2,
    )

    response = client.models.generate_content(
        model=get_model(),
        contents=contents,
        config=config,
    )

    text = getattr(response, "text", "") or ""
    sources = _extract_grounding_sources(response)

    response_id = (
        getattr(response, "response_id", None)
        or getattr(response, "id", None)
        or ""
    )

    return text, sources, str(response_id)
