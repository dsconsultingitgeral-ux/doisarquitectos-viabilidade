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
    # Mantém o modelo configurável, mas migra automaticamente um identificador antigo
    # usado nas versões anteriores da aplicação que não consta da lista oficial atual.
    configured = _secret("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if configured == "gemini-3.7-flash":
        logger.warning("GEMINI_MODEL=gemini-3.7-flash não é um endpoint oficial atual; a usar gemini-2.5-flash.")
        return "gemini-2.5-flash"
    return configured or "gemini-2.5-flash"


def get_fallback_models() -> list[str]:
    """Small, verified production fallback chain.

    Keeping the chain short is intentional: invalid/retired model probes were a major
    source of avoidable latency. The configured secret remains first; a stable Gemini
    2.5 Flash fallback is always available, followed by one current Flash fallback.
    """
    primary = get_model().strip() or "gemini-2.5-flash"
    raw = _secret("GEMINI_FALLBACK_MODELS", "")
    requested = [m.strip() for m in raw.split(",") if m.strip()]
    built_in = ["gemini-2.5-flash"]

    seen: set[str] = set()
    out: list[str] = []
    for model in [primary] + requested + built_in:
        if model and model not in seen:
            seen.add(model)
            out.append(model)
        if len(out) >= 2:
            break
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
            for attempt in range(1, 3):
                try:
                    uploaded = client.files.upload(file=temp_path)
                    uploaded = _wait_until_ready(client, uploaded, timeout_seconds=90)
                    break
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable_error(exc) or attempt == 2:
                        raise
                    delay = min(10.0, (1.7 ** attempt) + random.uniform(0.1, 0.8))
                    logger.warning(
                        "Temporary Gemini file-upload error (attempt %s/2): %s",
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
    """Return the most informative DECISÃO PRELIMINAR block.

    Some model responses can contain an initial placeholder block followed by the
    real populated block.  The old parser always selected the first one, which
    made the dashboard show only "A confirmar" even when the report below had
    confirmed values.  We score every decision block and keep the one with the
    greatest amount of concrete information.
    """
    source = text or ""
    pattern = re.compile(
        r"(?ims)^\s*(?:#+\s*)?DECISÃO PRELIMINAR\s*$\n(.*?)(?=^\s*(?:#+\s*)?(?:DECISÃO PRELIMINAR|\d+\.|RESUMO EXECUTIVO|IDENTIFICAÇÃO|DOCUMENTAÇÃO|ENQUADRAMENTO)|\Z)"
    )
    blocks = [m.group(1).strip() for m in pattern.finditer(source)]
    if not blocks:
        return ""

    labels = (
        "VIABILIDADE", "MELHOR APROVEITAMENTO", "ÁREA IDENTIFICADA",
        "CLASSIFICAÇÃO", "IMPLANTAÇÃO", "PISOS", "EVIDÊNCIA"
    )

    def score(block: str) -> tuple[int, int]:
        useful = 0
        concrete = 0
        upper = block.upper()
        for label in labels:
            m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", block)
            if not m:
                continue
            value = m.group(1).strip()
            useful += 1
            vu = value.upper()
            if value and "A CONFIRMAR" not in vu and "A VALIDAR" not in vu:
                concrete += 1
        # Prefer cited/grounded populated blocks when scores tie.
        citations = len(re.findall(r"\[\d+(?:\s*[,;]\s*\d+)*\]", block))
        return concrete * 100 + useful * 10 + citations, len(block)

    return max(blocks, key=score)

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


def _line_value_raw(block: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", block or "")
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def _has_citation(value: str) -> bool:
    return bool(re.search(r"\[\d+(?:\s*[,;]\s*\d+)*\]", value or ""))


def _without_citations(value: str) -> str:
    value = re.sub(r"\s*\[\d+(?:\s*[,;]\s*\d+)*\]", "", value or "")
    return _short_value(value)


def build_canonical_facts(analysis_text: str, sources: list[SourceLink] | None = None) -> dict:
    """Build conservative dashboard facts from the same final report.

    Critical regulatory values are shown only when they are single-valued and the
    report line carries a citation while real grounding sources were captured. If that
    evidence is missing, the UI says A confirmar instead of presenting model inference
    as a regulation.
    """
    block = _decision_block(analysis_text) or (analysis_text or "")
    sources = sources or []
    has_grounded_sources = bool(sources)

    raw_implantation = _line_value_raw(block, ("IMPLANTAÇÃO", "IMPLANTACAO"))
    raw_floors = _line_value_raw(block, ("PISOS",))

    def critical_value(raw: str) -> str:
        if not raw or _has_numeric_range(raw):
            return "A confirmar"
        if re.search(r"\d", raw) and (not has_grounded_sources or not _has_citation(raw)):
            return "A confirmar"
        return _without_citations(raw)

    implantation = critical_value(raw_implantation)
    floors = critical_value(raw_floors)

    classification_raw = _line_value_raw(block, ("CLASSIFICAÇÃO", "CLASSIFICACAO"))
    use_raw = _line_value_raw(block, ("MELHOR APROVEITAMENTO", "USO RECOMENDADO"))

    # Classification/use are still allowed as descriptive values when no numeric rule is
    # asserted, but the evidence badge remains A VALIDAR if grounding was not captured.
    facts = {
        "validated_location": _without_citations(_line_value_raw(block, ("LOCALIZAÇÃO", "LOCALIZACAO"))),
        "viability": _without_citations(_line_value_raw(block, ("VIABILIDADE",))),
        "area": _without_citations(_line_value_raw(block, ("ÁREA IDENTIFICADA", "AREA IDENTIFICADA", "ÁREA", "AREA"))),
        "classification": _without_citations(classification_raw),
        "recommended_use": _without_citations(use_raw),
        "implantation": implantation,
        "implantation_status": _status_from_value(implantation),
        "implantation_evidence": "Linha executiva citada + fontes grounded" if implantation != "A confirmar" else "Evidência insuficiente",
        "floors": floors,
        "floors_status": _status_from_value(floors),
        "floors_evidence": "Linha executiva citada + fontes grounded" if floors != "A confirmar" else "Evidência insuficiente",
        "height": "A confirmar",
        "height_status": "NÃO DETERMINADO",
        "utilization_index": "A confirmar",
        "utilization_index_status": "NÃO DETERMINADO",
        "impermeability": "A confirmar",
        "impermeability_status": "NÃO DETERMINADO",
        "evidence_status": "REFERENCIADO" if has_grounded_sources else "A VALIDAR",
        "notes": [],
    }

    if implantation == "A confirmar" or floors == "A confirmar":
        facts["evidence_status"] = "A VALIDAR"
        facts["notes"].append("Pelo menos um parâmetro regulamentar crítico não ficou sustentado por valor único + citação + fonte grounded.")

    for k in ("validated_location", "viability", "area", "classification", "recommended_use"):
        if not facts[k] or facts[k] in {"—", "-"}:
            facts[k] = "" if k == "validated_location" else "A confirmar"
    return facts

def _replace_decision_block(text: str, facts: dict) -> str:
    """Render exactly one executive block and keep the technical body once.

    The previous regex could replace only the first placeholder block and leave a
    second DECISÃO PRELIMINAR immediately underneath.  For client output we keep
    one clean executive block and start the body at section 1.
    """
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

    source = (text or "").strip()
    # The technical report is contractually sectioned.  Preserve everything from
    # section 1 onward and replace any duplicated/placeholder preamble.
    m = re.search(r"(?im)^\s*(?:#+\s*)?1\.\s*RESUMO EXECUTIVO\s*$", source)
    if m:
        body = source[m.start():].lstrip()
        return (block + "\n\n" + body).strip()

    # Defensive fallback for unusual output: remove every short decision block.
    pattern = re.compile(
        r"(?ims)^\s*(?:#+\s*)?DECISÃO PRELIMINAR\s*$.*?(?=^\s*(?:#+\s*)?(?:DECISÃO PRELIMINAR|\d+\.|RESUMO EXECUTIVO|IDENTIFICAÇÃO|DOCUMENTAÇÃO|ENQUADRAMENTO)|\Z)"
    )
    body = pattern.sub("", source).strip()
    return (block + "\n\n" + body).strip()

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
        per_model_attempts = max(1, min(2, attempts_per_model + (1 if model_index == 0 else 0)))

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
                    delay = min(3.0, 0.8 + (0.8 * attempt) + random.uniform(0.05, 0.25))
                    time.sleep(delay)

        # A tiny pause prevents an immediate burst against the next model endpoint.
        if model_index < len(models) - 1:
            time.sleep(0.15)

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




def _local_document_manifest(files: Iterable[Any]) -> tuple[str, bool]:
    """Build a deterministic document index before Gemini analysis.

    This does not replace visual/PDF analysis. It guarantees that every uploaded
    filename and any machine-readable project signals are explicitly present in
    the model context, preventing an architectural study from being silently
    ignored when several PDFs are uploaded together.
    """
    entries = []
    project_candidate = False

    for idx, f in enumerate(list(files), 1):
        name = getattr(f, "name", f"documento_{idx}")
        suffix = Path(name).suffix.lower()
        raw = f.getvalue()
        text = ""

        try:
            if suffix == ".pdf":
                from io import BytesIO
                from pypdf import PdfReader
                reader = PdfReader(BytesIO(raw))
                chunks = []
                for page_no, page in enumerate(reader.pages[:20], 1):
                    try:
                        t = page.extract_text() or ""
                    except Exception:
                        t = ""
                    if t.strip():
                        chunks.append(f"[p.{page_no}] {t}")
                    if sum(len(x) for x in chunks) >= 18000:
                        break
                text = "\n".join(chunks)[:18000]
            elif suffix == ".txt":
                text = raw.decode("utf-8", errors="ignore")[:18000]
            elif suffix == ".docx":
                try:
                    from io import BytesIO
                    from docx import Document
                    doc = Document(BytesIO(raw))
                    text = "\n".join(p.text for p in doc.paragraphs)[:18000]
                except Exception:
                    text = ""
        except Exception as exc:
            logger.info("Local text extraction unavailable for %s: %s", name, exc)

        normalized = re.sub(r"\s+", " ", text).upper()
        project_signals = (
            "PROJECTO DE ARQUITECTURA", "PROJETO DE ARQUITETURA",
            "FASE PROJECTO", "FASE PROJETO", "ESTUDO - OPÇÃO",
            "ESTUDO - OPCAO", "PROPOSTA . PLANTAS",
            "PLANTA DE IMPLANTAÇÃO", "PLANTA DE IMPLANTACAO",
            "CONSTRUÇÃO DE EDIFÍCIOS", "CONSTRUCAO DE EDIFICIOS",
            "HABITAÇÃO MULTIFAMILIAR", "HABITACAO MULTIFAMILIAR",
            "PEDIDO DE INFORMAÇÃO PRÉVIA", "PEDIDO DE INFORMACAO PREVIA",
        )
        is_project = any(sig in normalized for sig in project_signals)
        if is_project:
            project_candidate = True
            kind = "PROJETO/ESTUDO/PIP CANDIDATO — analisar obrigatoriamente como proposta arquitetónica"
        elif any(sig in normalized for sig in ("LEVANTAMENTO TOPOGRÁFICO", "LEVANTAMENTO TOPOGRAFICO", "COTAS")):
            kind = "LEVANTAMENTO/TOPOGRAFIA CANDIDATO"
        elif any(sig in normalized for sig in ("PLANTA DE ORDENAMENTO", "PLANTA DE CONDICIONANTES", "CARTOGRAFIA ESCALA", "PDM")):
            kind = "CARTOGRAFIA/PDM CANDIDATO"
        else:
            kind = "DOCUMENTO A CLASSIFICAR PELO MODELO"

        excerpt = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not excerpt:
            excerpt = "[Sem texto extraível localmente; ler visualmente o ficheiro anexado.]"

        entries.append(
            f"DOCUMENTO {idx}\n"
            f"NOME ORIGINAL: {name}\n"
            f"CLASSIFICAÇÃO PRÉVIA: {kind}\n"
            f"TEXTO EXTRAÍDO LOCALMENTE (auxiliar, não substitui leitura visual):\n{excerpt}"
        )

    header = (
        "ÍNDICE DETERMINÍSTICO DOS DOCUMENTOS CARREGADOS\n"
        f"TOTAL DE FICHEIROS: {len(entries)}\n"
        "REGRA: nenhum ficheiro deste índice pode ser ignorado. Se existir um "
        "PROJETO/ESTUDO/PIP CANDIDATO, é proibido concluir que não há proposta "
        "sem primeiro o analisar visualmente e extrair o respetivo quadro-síntese/planta.\n\n"
    )
    return header + "\n\n".join(entries), project_candidate


def _report_denies_existing_project(text: str) -> bool:
    t = (text or "").lower()
    markers = (
        "não foi anexada proposta arquitetónica",
        "nao foi anexada proposta arquitetonica",
        "sem proposta arquitetónica anexada",
        "sem proposta arquitetonica anexada",
        "ausência de projeto desenhado",
        "ausencia de projeto desenhado",
        "não foi anexado projeto de arquitetura",
        "nao foi anexado projeto de arquitetura",
    )
    return any(m in t for m in markers)


def run_full_analysis(prompt: str, uploaded_files: Iterable[Any]):
    """V5.1 FAST + SAFE: one grounded AI call per study.

    The previous V5 could execute draft + independent review + repair + canonical
    extraction, which made a normal study take several model round-trips. V5.1 keeps
    the same UI but performs one researched generation, then only deterministic/local
    consistency checks. If an ambiguous maximum survives, it is withheld rather than
    triggering another slow AI pass.
    """
    client = get_client()
    uploaded_files = list(uploaded_files or [])

    # Local pre-index: fast, zero extra API calls, and guarantees that the model
    # sees every original filename + machine-readable project evidence.
    document_manifest, project_candidate = _local_document_manifest(uploaded_files)
    gemini_files = upload_files(uploaded_files)

    contents: list[Any] = [prompt, document_manifest]
    # Keep each original name immediately adjacent to the corresponding Gemini
    # file reference. The Files API may otherwise expose an opaque/temp name.
    for idx, (original, gemini_file) in enumerate(zip(uploaded_files, gemini_files), 1):
        contents.append(
            f"DOCUMENTO ANEXADO {idx}/{len(gemini_files)} — NOME ORIGINAL: {getattr(original, 'name', f'documento_{idx}')}"
        )
        contents.append(gemini_file)

    response = _generate_grounded_resilient(
        client,
        contents,
        temperature=0.01,
        attempts_per_model=1,
    )
    final_text = getattr(response, "text", "") or ""

    # Safety net: if a project/PIP was deterministically detected in the uploads
    # but the model still says there is no proposal, redo exactly once with a
    # focused instruction. This avoids shipping a structurally wrong report.
    if project_candidate and _report_denies_existing_project(final_text):
        correction = (
            "CORREÇÃO OBRIGATÓRIA: o índice documental contém pelo menos um "
            "PROJETO/ESTUDO/PIP CANDIDATO. A resposta anterior ignorou-o. Refaça "
            "o relatório completo desde o início, lendo esse anexo visualmente. "
            "A secção 4 deve transcrever os valores da proposta (áreas, pisos, "
            "fogos/tipologias, estacionamento, caves e quadro-síntese quando "
            "existirem) e a secção 7 deve confrontar PROPOSTA × REGULAMENTO. "
            "É proibido escrever que não existe proposta."
        )
        retry_contents = [prompt, document_manifest, correction]
        for idx, (original, gemini_file) in enumerate(zip(uploaded_files, gemini_files), 1):
            retry_contents.append(
                f"DOCUMENTO ANEXADO {idx}/{len(gemini_files)} — NOME ORIGINAL: {getattr(original, 'name', f'documento_{idx}')}"
            )
            retry_contents.append(gemini_file)
        response = _generate_grounded_resilient(
            client, retry_contents, temperature=0.0, attempts_per_model=1
        )
        final_text = getattr(response, "text", "") or final_text

    final_text = _enforce_client_maximum_rules(final_text)

    sources = _extract_grounding_sources(response)
    response_id = getattr(response, "response_id", None) or getattr(response, "id", None) or ""

    # Zero API calls: UI and PDF consume exactly the same completed report.
    summary = build_canonical_facts(final_text, sources=sources)
    final_text = _replace_decision_block(final_text, summary)
    return final_text, sources, str(response_id), summary

