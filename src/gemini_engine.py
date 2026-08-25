from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any
from pathlib import Path
import os
import tempfile
import time
import hashlib
import json
import re

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]


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
    # Mantém o modelo configurável nos Secrets, sem expor chaves ou configuração privada no GitHub.
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
            return current

    return current


def upload_files(files: Iterable[Any]) -> list[Any]:
    """Upload Streamlit files to Gemini Files API with a session cache."""
    client = get_client()
    uploaded_files = []

    try:
        import streamlit as st
        cache = st.session_state.setdefault("_gemini_file_cache", {})
    except Exception:
        cache = {}

    for f in files:
        raw = f.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        cached_name = cache.get(digest)

        if cached_name:
            try:
                uploaded = client.files.get(name=cached_name)
                uploaded = _wait_until_ready(client, uploaded)
                uploaded_files.append(uploaded)
                continue
            except Exception:
                cache.pop(digest, None)

        suffix = Path(f.name).suffix or ".bin"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(raw)
                temp_path = tmp.name

            uploaded = client.files.upload(file=temp_path)
            uploaded = _wait_until_ready(client, uploaded)
            uploaded_files.append(uploaded)

            if getattr(uploaded, "name", None):
                cache[digest] = uploaded.name
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


def _safe_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        pass

    # Defensive fallback for models that wrap JSON in a fenced block.
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _load_executive_summary_prompt() -> str:
    path = ROOT / "prompts" / "executive_summary_prompt.txt"
    return path.read_text(encoding="utf-8")


def build_executive_summary(analysis_text: str) -> dict:
    """Create a small structured view model for the Module 4 cards.

    This call is deliberately NOT grounded and receives only the finished report.
    It cannot introduce new urbanistic facts; it only reformats existing content.
    """
    if not (analysis_text or "").strip():
        return {}

    client = get_client()
    prompt = _load_executive_summary_prompt()
    contents = f"{prompt}\n\nRELATÓRIO A EXTRAIR:\n{analysis_text[:70000]}"

    try:
        response = client.models.generate_content(
            model=get_model(),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        return _safe_json(getattr(response, "text", "") or "")
    except Exception:
        # The application remains functional even if the secondary formatting call fails.
        return {}


def _load_quality_gate_prompt() -> str:
    return (ROOT / "prompts" / "quality_gate_prompt.txt").read_text(encoding="utf-8")


def _load_repair_prompt() -> str:
    return (ROOT / "prompts" / "repair_prompt.txt").read_text(encoding="utf-8")


def _quality_issues(text: str) -> list[str]:
    """Cheap deterministic checks for the two failure modes found in real-case validation."""
    t = (text or "").lower()
    issues: list[str] = []

    # Every final study must explicitly assess multifamily housing.
    if "habitação multifamiliar" not in t and "habitacao multifamiliar" not in t:
        issues.append("A matriz/relatório não avalia explicitamente Habitação Multifamiliar.")

    # Never invent a reference parcel when the real area is unknown.
    forbidden_area_phrases = [
        "área hipotética", "area hipotetica", "lote hipotético", "lote hipotetico",
        "parcela hipotética", "parcela hipotetica", "lote conceptual", "parcela tipo",
        "terreno hipotético", "terreno hipotetico", "simulação teórica a 1.000",
        "simulacao teorica a 1.000", "referência de 1.000 m", "referencia de 1.000 m",
    ]
    if any(x in t for x in forbidden_area_phrases):
        issues.append("Foi criada uma área/lote hipotético para calcular valores absolutos.")

    # Three scenarios are mandatory in the final report.
    for code in ("cenário a", "cenário b", "cenário c"):
        if code not in t and code.replace("á", "a") not in t:
            issues.append(f"Falta {code.upper()} no relatório final.")

    return issues


def _generate_grounded(client: genai.Client, model: str, contents: list[Any], temperature: float = 0.08):
    google_search = types.Tool(google_search=types.GoogleSearch())
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[google_search],
            temperature=temperature,
        ),
    )


def run_full_analysis(prompt: str, uploaded_files: Iterable[Any]):
    """Two-pass grounded analysis with an optional deterministic repair pass.

    Pass 1 researches and drafts. Pass 2 independently reviews the draft against hard
    quality rules using the same parcel documents and web grounding. A third pass only
    runs when deterministic checks still detect a known critical failure.
    """
    client = get_client()
    model = get_model()
    gemini_files = upload_files(uploaded_files)

    # PASS 1 — research + technical draft.
    draft_contents: list[Any] = [prompt]
    draft_contents.extend(gemini_files)
    draft_response = _generate_grounded(client, model, draft_contents, temperature=0.10)
    draft_text = getattr(draft_response, "text", "") or ""

    # PASS 2 — final independent quality gate. It sees the same files and may search
    # official sources again, so the final answer is not merely a stylistic rewrite.
    review_prompt = _load_quality_gate_prompt()
    review_contents: list[Any] = [
        prompt,
        review_prompt,
        "\n\nRASCUNHO TÉCNICO A REVER E SUBSTITUIR:\n" + draft_text[:90000],
    ]
    review_contents.extend(gemini_files)
    final_response = _generate_grounded(client, model, review_contents, temperature=0.05)
    final_text = getattr(final_response, "text", "") or draft_text

    # PASS 3 — only if a known critical regression survives pass 2.
    issues = _quality_issues(final_text)
    if issues:
        repair_contents: list[Any] = [
            prompt,
            _load_quality_gate_prompt(),
            _load_repair_prompt(),
            "\nFALHAS DETETADAS AUTOMATICAMENTE:\n- " + "\n- ".join(issues),
            "\n\nRELATÓRIO A CORRIGIR:\n" + final_text[:90000],
        ]
        repair_contents.extend(gemini_files)
        repaired = _generate_grounded(client, model, repair_contents, temperature=0.02)
        repaired_text = getattr(repaired, "text", "") or ""
        if repaired_text.strip():
            final_response = repaired
            final_text = repaired_text

    sources = _extract_grounding_sources(final_response)
    response_id = (
        getattr(final_response, "response_id", None)
        or getattr(final_response, "id", None)
        or ""
    )

    summary = build_executive_summary(final_text)
    return final_text, sources, str(response_id), summary
