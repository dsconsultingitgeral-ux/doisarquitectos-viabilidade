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
import random
import logging

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
    # Mantém o modelo principal configurável nos Secrets, sem expor chaves no GitHub.
    return _secret("GEMINI_MODEL", "gemini-3.7-flash")


def get_fallback_models() -> list[str]:
    """Build a production-safe fallback chain using current GA Gemini 3 models.

    The Streamlit secret GEMINI_MODEL is respected as the first preference, but the
    application always keeps several stable fallbacks. Old Gemini 2.x model names are
    deliberately ignored because they may return 404 for newer API users.
    """
    primary = get_model().strip()
    raw = _secret("GEMINI_FALLBACK_MODELS", "")

    # Current stable text/multimodal production fallbacks (Aug 2026).
    built_in = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]

    requested = [m.strip() for m in raw.split(",") if m.strip()]
    models = [primary] + requested + built_in

    seen: set[str] = set()
    out: list[str] = []
    for model in models:
        if not model or model in seen:
            continue
        # Never let a stale 2.x secret break the whole chain.
        if model.startswith("gemini-2."):
            logger.warning("Ignoring retired/stale Gemini fallback model: %s", model)
            continue
        seen.add(model)
        out.append(model)
    return out


class AIServiceTemporarilyUnavailable(RuntimeError):
    """Raised only after retries/fallbacks for a temporary upstream failure are exhausted."""


logger = logging.getLogger(__name__)


def _is_retryable_error(exc: Exception) -> bool:
    """Recognise transient Gemini/network failures without depending on one SDK exception class."""
    text = f"{type(exc).__name__}: {exc}".lower()
    transient_markers = (
        "429", "500", "502", "503", "504",
        "resource_exhausted", "unavailable", "deadline_exceeded",
        "high demand", "temporarily", "timeout", "timed out",
        "connection reset", "connection aborted", "connection error",
        "service unavailable", "internal server error",
    )
    return any(marker in text for marker in transient_markers)


def _is_model_unavailable_error(exc: Exception) -> bool:
    """Errors that mean 'skip this model and continue with the next one'."""
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "404", "not_found", "not found", "no longer available",
        "model is not found", "model not found", "unsupported model",
        "does not support", "not supported for this model",
    )
    return any(marker in text for marker in markers)


def _friendly_upstream_message(exc: Exception) -> str:
    if _is_retryable_error(exc):
        return (
            "O serviço de inteligência artificial está temporariamente congestionado. "
            "A aplicação tentou novamente de forma automática, mas o serviço externo ainda não respondeu. "
            "Tente novamente dentro de alguns instantes; os dados introduzidos permanecem nesta sessão."
        )
    return (
        "Não foi possível concluir a análise neste momento. "
        "Os dados introduzidos permanecem nesta sessão; tente novamente ou contacte o suporte se o problema persistir."
    )


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
    """Upload Streamlit files to Gemini Files API with cache + retries.

    A temporary upload/network failure must not abort a client study immediately.
    """
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

            last_exc: Exception | None = None
            uploaded = None
            for attempt in range(1, 5):
                try:
                    uploaded = client.files.upload(file=temp_path)
                    uploaded = _wait_until_ready(client, uploaded, timeout_seconds=120)
                    break
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable_error(exc) or attempt == 4:
                        raise
                    delay = min(10.0, (1.7 ** attempt) + random.uniform(0.1, 0.8))
                    logger.warning(
                        "Temporary Gemini file-upload error (attempt %s/4): %s",
                        attempt, exc,
                    )
                    time.sleep(delay)

            if uploaded is None:
                if last_exc:
                    raise last_exc
                raise RuntimeError("Não foi possível preparar o documento para análise.")

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


def _load_canonical_facts_prompt() -> str:
    return (ROOT / "prompts" / "canonical_facts_prompt.txt").read_text(encoding="utf-8")


def _short_value(value: Any, fallback: str = "A confirmar") -> str:
    value = str(value or "").strip()
    if not value or value.lower() in {"none", "null", "—", "-"}:
        return fallback
    return re.sub(r"\s+", " ", value)[:160]


def _decision_block(text: str) -> str:
    """Return the short executive block without any additional AI call."""
    m = re.search(
        r"(?ims)^\s*(?:#+\s*)?DECISÃO PRELIMINAR\s*$\n(.*?)(?=^\s*(?:#+\s*)?(?:1\.|1\s|RESUMO EXECUTIVO|IDENTIFICAÇÃO|DOCUMENTAÇÃO|ENQUADRAMENTO)|\Z)",
        text or "",
    )
    return (m.group(1) if m else "").strip()


def _line_value(block: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", block or "")
        if m:
            return _short_value(m.group(1))
    return "A confirmar"


def _status_from_value(value: str) -> str:
    v = (value or "").upper()
    if "A CONFIRMAR" in v or "A VALIDAR" in v or "NÃO DETERMINADO" in v:
        return "A VALIDAR"
    if value and value != "A confirmar":
        return "PROVÁVEL"
    return "NÃO DETERMINADO"


def _has_numeric_range(value: str) -> bool:
    return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:a|–|—|-)\s*\d+(?:[.,]\d+)?", value or "", re.I))


def _withhold_ambiguous_max(value: str) -> str:
    """Never expose a merged/range value as a regulatory maximum.

    The client explicitly requires one applicable maximum. When the model has merged
    regimes/categories into a range, withholding the value is safer than inventing a
    maximum from the upper bound.
    """
    if _has_numeric_range(value):
        return "A confirmar"
    return _short_value(value)


def build_canonical_facts(analysis_text: str) -> dict:
    """Build the dashboard record locally from the SAME final report.

    V5.1 intentionally performs zero extra Gemini calls here. This removes the former
    fourth request per study and guarantees that dashboard and PDF derive from one
    completed text only.
    """
    block = _decision_block(analysis_text)
    if not block:
        block = analysis_text or ""

    implantation = _withhold_ambiguous_max(_line_value(block, ("IMPLANTAÇÃO", "IMPLANTACAO")))
    floors = _withhold_ambiguous_max(_line_value(block, ("PISOS",)))

    facts = {
        "validated_location": _line_value(block, ("LOCALIZAÇÃO", "LOCALIZACAO")),
        "viability": _line_value(block, ("VIABILIDADE",)),
        "area": _line_value(block, ("ÁREA IDENTIFICADA", "AREA IDENTIFICADA", "ÁREA", "AREA")),
        "classification": _line_value(block, ("CLASSIFICAÇÃO", "CLASSIFICACAO")),
        "recommended_use": _line_value(block, ("MELHOR APROVEITAMENTO", "USO RECOMENDADO")),
        "implantation": implantation,
        "implantation_status": _status_from_value(implantation),
        "implantation_evidence": "Bloco executivo do relatório final",
        "floors": floors,
        "floors_status": _status_from_value(floors),
        "floors_evidence": "Bloco executivo do relatório final",
        "height": "A confirmar",
        "height_status": "NÃO DETERMINADO",
        "utilization_index": "A confirmar",
        "utilization_index_status": "NÃO DETERMINADO",
        "impermeability": "A confirmar",
        "impermeability_status": "NÃO DETERMINADO",
        "evidence_status": "NÃO DETERMINADO",
        "notes": [],
    }

    statuses = [facts["implantation_status"], facts["floors_status"]]
    if statuses and all(x == "PROVÁVEL" for x in statuses):
        facts["evidence_status"] = "PROVÁVEL"
    elif any(x == "A VALIDAR" for x in statuses):
        facts["evidence_status"] = "A VALIDAR"

    if facts["validated_location"] == "A confirmar":
        # Do not invent a location; the UI will fall back to session location.
        facts["validated_location"] = ""
    return facts

def _replace_decision_block(text: str, facts: dict) -> str:
    """Force the visible executive block to use the exact same canonical values as the cards/PDF."""
    if not facts:
        return text

    block = "\n".join([
        "DECISÃO PRELIMINAR",
        f"VIABILIDADE: {_short_value(facts.get('viability'))}",
        f"MELHOR APROVEITAMENTO: {_short_value(facts.get('recommended_use'))}",
        f"ÁREA IDENTIFICADA: {_short_value(facts.get('area'))}",
        f"CLASSIFICAÇÃO: {_short_value(facts.get('classification'))}",
        f"IMPLANTAÇÃO: {_short_value(facts.get('implantation'))}",
        f"PISOS: {_short_value(facts.get('floors'))}",
        f"EVIDÊNCIA: {_short_value(facts.get('evidence_status'), 'NÃO DETERMINADO')}",
    ])

    pattern = re.compile(
        r"(?ims)^\s*(?:#+\s*)?DECISÃO PRELIMINAR\s*$.*?(?=^\s*(?:#+\s*)?(?:1\.|1\s|IDENTIFICAÇÃO|DOCUMENTAÇÃO|RESUMO|ENQUADRAMENTO|##\s)|\Z)"
    )
    if pattern.search(text or ""):
        return pattern.sub(block + "\n\n", text, count=1).strip()
    return (block + "\n\n" + (text or "")).strip()


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

    # Secondary UI formatting must never make the completed study fail.
    for model in get_fallback_models():
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            parsed = _safe_json(getattr(response, "text", "") or "")
            if parsed:
                return parsed
        except Exception as exc:
            if _is_model_unavailable_error(exc) or _is_retryable_error(exc):
                continue
            break
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

    # Client-critical regression: regulatory maxima must not be presented as invented ranges.
    # We only police the executive block here; scenario ranges elsewhere may be legitimate.
    decision_match = re.search(r"(?is)decisão preliminar(.*?)(?:\n\s*#|\n\s*1[. —-]|\Z)", text or "")
    decision = decision_match.group(1) if decision_match else ""
    if decision:
        for label in ("PISOS", "IMPLANTAÇÃO"):
            m = re.search(rf"(?im)^\s*{label}\s*:\s*(.+)$", decision)
            if m:
                value = m.group(1).strip()
                if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:a|–|—|-)\s*\d+(?:[.,]\d+)?", value, re.I):
                    issues.append(f"{label} surge como intervalo no bloco executivo; usar o máximo regulamentar exato ou A CONFIRMAR.")

    return issues


def _generate_grounded_once(client: genai.Client, model: str, contents: list[Any], temperature: float = 0.08):
    google_search = types.Tool(google_search=types.GoogleSearch())
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[google_search],
            temperature=temperature,
            top_p=0.25,
            candidate_count=1,
        ),
    )


def _generate_grounded_resilient(
    client: genai.Client,
    contents: list[Any],
    temperature: float = 0.08,
    attempts_per_model: int = 2,
):
    """Production resilience for model congestion and model retirement.

    Strategy:
      1. Try the configured model first.
      2. Retry transient 429/5xx/network failures with exponential backoff.
      3. If a model is missing/retired/unsupported, skip it immediately.
      4. Continue through several current GA Gemini 3 models.
      5. Only fail after the complete chain is exhausted.
    """
    last_exc: Exception | None = None
    models = get_fallback_models()

    for model_index, model in enumerate(models):
        per_model_attempts = 3 if model_index == 0 else attempts_per_model

        for attempt in range(1, per_model_attempts + 1):
            try:
                logger.info("Gemini analysis call: model=%s attempt=%s/%s", model, attempt, per_model_attempts)
                return _generate_grounded_once(client, model, contents, temperature)
            except Exception as exc:
                last_exc = exc

                if _is_model_unavailable_error(exc):
                    logger.warning("Gemini model unavailable/unsupported; skipping %s: %s", model, exc)
                    break

                if not _is_retryable_error(exc):
                    # A model-specific 4xx/tool incompatibility should not prevent us
                    # trying the remaining production models. Authentication/key errors
                    # are the important exception: retrying other models cannot fix them.
                    text = f"{type(exc).__name__}: {exc}".lower()
                    auth_error = any(x in text for x in (
                        "401", "403", "api key", "permission_denied", "unauthenticated",
                        "billing", "quota has been disabled",
                    ))
                    if auth_error:
                        logger.exception("Gemini authentication/configuration error")
                        raise

                    logger.warning("Gemini model-specific error; trying next model %s: %s", model, exc)
                    break

                logger.warning(
                    "Temporary Gemini error using model %s (attempt %s/%s): %s",
                    model, attempt, per_model_attempts, exc,
                )
                if attempt < per_model_attempts:
                    delay = min(12.0, (1.8 ** attempt) + random.uniform(0.25, 1.0))
                    time.sleep(delay)

        # A tiny pause prevents an immediate burst against the next model endpoint.
        if model_index < len(models) - 1:
            time.sleep(random.uniform(0.35, 0.9))

    if last_exc is not None:
        raise AIServiceTemporarilyUnavailable(_friendly_upstream_message(last_exc)) from last_exc
    raise AIServiceTemporarilyUnavailable("O serviço de IA não está disponível neste momento.")


def _enforce_client_maximum_rules(text: str) -> str:
    """Deterministic safety pass for the exact client complaint.

    We do NOT guess the upper number of an ambiguous range. A regulatory maximum must
    be one supported value. If the model still outputs a numeric range for the two
    client-critical executive fields, the value is withheld as A CONFIRMAR.
    """
    if not text:
        return text

    lines = text.splitlines()
    out = []
    decision = False
    for raw in lines:
        stripped = raw.strip()
        upper = stripped.upper().lstrip("# ").strip()
        if upper == "DECISÃO PRELIMINAR":
            decision = True
            out.append(raw)
            continue
        if decision and re.match(r"^(?:#+\s*)?(?:1\.|1\s|RESUMO EXECUTIVO|IDENTIFICAÇÃO|DOCUMENTAÇÃO|ENQUADRAMENTO)", stripped, re.I):
            decision = False

        if decision:
            m = re.match(r"(?i)^(\s*)(IMPLANTAÇÃO|IMPLANTACAO|PISOS)(\s*:\s*)(.*)$", raw)
            if m and _has_numeric_range(m.group(4)):
                raw = f"{m.group(1)}{m.group(2)}{m.group(3)}A CONFIRMAR - não foi identificado um único máximo regulamentar inequívoco"

        # Also prevent the dedicated regulatory-parameter lines from calling a range
        # a confirmed maximum later in the report.
        if re.search(r"(?i)(número\s+máximo\s+de\s+pisos|índice\s+de\s+implantação.*máximo|implantação\s+máxima)", raw) and _has_numeric_range(raw):
            label = raw.split(":", 1)[0] if ":" in raw else "Parâmetro regulamentar"
            raw = f"{label}: A CONFIRMAR - a documentação/fonte aplicável não permitiu fixar um único máximo com segurança."
        out.append(raw)
    return "\n".join(out).strip()


def run_full_analysis(prompt: str, uploaded_files: Iterable[Any]):
    """V5.1 FAST + SAFE: one grounded AI call per study.

    The previous V5 could execute draft + independent review + repair + canonical
    extraction, which made a normal study take several model round-trips. V5.1 keeps
    the same UI but performs one researched generation, then only deterministic/local
    consistency checks. If an ambiguous maximum survives, it is withheld rather than
    triggering another slow AI pass.
    """
    client = get_client()
    gemini_files = upload_files(uploaded_files)

    contents: list[Any] = [prompt]
    contents.extend(gemini_files)
    response = _generate_grounded_resilient(
        client,
        contents,
        temperature=0.02,
        attempts_per_model=1,
    )
    final_text = getattr(response, "text", "") or ""
    final_text = _enforce_client_maximum_rules(final_text)

    sources = _extract_grounding_sources(response)
    response_id = getattr(response, "response_id", None) or getattr(response, "id", None) or ""

    # Zero API calls: UI and PDF consume exactly the same completed report.
    summary = build_canonical_facts(final_text)
    final_text = _replace_decision_block(final_text, summary)
    return final_text, sources, str(response_id), summary

