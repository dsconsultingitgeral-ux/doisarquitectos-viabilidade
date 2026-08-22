from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Any
import os
from openai import OpenAI

@dataclass
class SourceLink:
    index: int
    title: str
    url: str

def get_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            key = ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    return OpenAI(api_key=key)

def get_model() -> str:
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_MODEL", "gpt-5.6-terra")
    except Exception:
        return os.getenv("OPENAI_MODEL", "gpt-5.6-terra")

def upload_files(files: Iterable[Any]) -> list[str]:
    client = get_client()
    ids = []
    for f in files:
        # Streamlit UploadedFile behaves like a binary file object.
        f.seek(0)
        created = client.files.create(file=(f.name, f.getvalue()), purpose="user_data")
        ids.append(created.id)
    return ids

def _extract_url_sources(response) -> list[SourceLink]:
    found = []
    seen = set()
    # The SDK response shape can evolve. Traverse defensively.
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            annotations = getattr(content, "annotations", []) or []
            for ann in annotations:
                ann_type = getattr(ann, "type", None)
                if ann_type not in ("url_citation", "citation"):
                    continue
                url = getattr(ann, "url", None)
                title = getattr(ann, "title", None)
                if not url:
                    nested = getattr(ann, "url_citation", None)
                    if nested:
                        url = getattr(nested, "url", None)
                        title = title or getattr(nested, "title", None)
                if url and url not in seen:
                    seen.add(url)
                    found.append(SourceLink(len(found)+1, title or "Fonte consultada", url))
    return found

def run_full_analysis(prompt: str, uploaded_files: Iterable[Any]):
    client = get_client()
    file_ids = upload_files(uploaded_files)

    content = [{"type": "input_text", "text": prompt}]
    for file_id in file_ids:
        content.append({"type": "input_file", "file_id": file_id})

    response = client.responses.create(
        model=get_model(),
        input=[{"role": "user", "content": content}],
        tools=[{"type": "web_search"}],
        tool_choice="auto",
    )

    text = getattr(response, "output_text", "") or ""
    sources = _extract_url_sources(response)
    return text, sources, getattr(response, "id", "")
