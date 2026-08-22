from __future__ import annotations
import json
import random
import time
from typing import Any, Dict, List
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_TIMEOUT_MS
from core.utils import safe_json_loads
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.document_prompt import DOCUMENT_PROMPT
from prompts.web_prompt import WEB_RESEARCH_PROMPT
from prompts.synthesis_prompt import SYNTHESIS_PROMPT
from prompts.scenario_prompt import SCENARIO_PROMPT


class GeminiTemporarilyUnavailable(RuntimeError):
    pass


class GeminiService:
    def __init__(self, api_key: str = "", model: str = ""):
        key = api_key or GEMINI_API_KEY
        if not key:
            raise RuntimeError("GEMINI_API_KEY não configurada.")
        self.client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
        )
        self.model = model or GEMINI_MODEL
        self.models = []
        for m in [self.model] + list(GEMINI_FALLBACK_MODELS):
            if m and m not in self.models:
                self.models.append(m)
        self.last_model_used = None

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        text = str(exc).lower()
        needles = [
            "503", "unavailable", "high demand", "overloaded", "capacity",
            "429", "resource_exhausted", "rate limit", "504", "deadline_exceeded", "timeout",
        ]
        return any(n in text for n in needles)

    def _generate(self, *, contents, config, operation: str = "análise"):
        errors = []
        # Um pedido por modelo. É deliberadamente rápido: em caso de 503 passa logo
        # para outro endpoint estável em vez de fazer o utilizador esperar vários minutos.
        for idx, model in enumerate(self.models):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                self.last_model_used = model
                return response
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                if not self._is_retryable(exc):
                    raise
                # Pequeno backoff antes do fallback seguinte, como recomendado para 429/503.
                if idx < len(self.models) - 1:
                    time.sleep(min(2.0 + idx * 1.5 + random.random(), 5.0))

        raise GeminiTemporarilyUnavailable(
            f"O serviço Gemini está temporariamente congestionado para {operation}. "
            "Foram tentados automaticamente vários modelos. Tente novamente dentro de alguns instantes."
        )

    def analyze_documents(self, uploaded_files) -> Dict[str, Any]:
        contents = []
        manifest = []
        for f in uploaded_files:
            data = f.getvalue()
            mime = getattr(f, "type", None) or "application/pdf"
            manifest.append({"filename": f.name, "mime_type": mime, "size": len(data)})
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
            contents.append(f"NOME_DO_FICHEIRO: {f.name}")
        prompt = SYSTEM_PROMPT + "\n\n" + DOCUMENT_PROMPT + "\n\nMANIFESTO:\n" + json.dumps(manifest, ensure_ascii=False)
        contents.append(prompt)
        response = self._generate(
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
            operation="análise documental",
        )
        data = safe_json_loads(response.text)
        if isinstance(data, dict):
            data["_model_used"] = self.last_model_used
        return data

    def web_research(self, study_context: Dict[str, Any], document_context: Dict[str, Any]) -> Dict[str, Any]:
        # Não usar str.format() aqui: os prompts contêm blocos JSON com chavetas.
        # Substituição explícita evita KeyError em chaves como "identification".
        web_prompt = WEB_RESEARCH_PROMPT
        web_prompt = web_prompt.replace("{study_context}", json.dumps(study_context, ensure_ascii=False, indent=2))
        web_prompt = web_prompt.replace("{document_context}", json.dumps(document_context, ensure_ascii=False, indent=2)[:45000])
        prompt = SYSTEM_PROMPT + "\n\n" + web_prompt
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        response = self._generate(
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, tools=[grounding_tool]),
            operation="pesquisa territorial",
        )
        citations = []
        try:
            gm = response.candidates[0].grounding_metadata
            for ch in (gm.grounding_chunks or []):
                if getattr(ch, "web", None):
                    url = ch.web.uri or ""
                    title = ch.web.title or ""
                    if url and not any(x.get("url") == url for x in citations):
                        citations.append({"title": title, "url": url})
            queries = list(gm.web_search_queries or [])
        except Exception:
            queries = []
        return {
            "text": response.text or "",
            "citations": citations,
            "queries": queries,
            "model_used": self.last_model_used,
        }

    def synthesize_rules(self, study_context: Dict[str, Any], document_context: Dict[str, Any], web_context: Dict[str, Any]) -> Dict[str, Any]:
        synthesis_prompt = SYNTHESIS_PROMPT
        synthesis_prompt = synthesis_prompt.replace("{study_context}", json.dumps(study_context, ensure_ascii=False, indent=2))
        synthesis_prompt = synthesis_prompt.replace("{document_context}", json.dumps(document_context, ensure_ascii=False, indent=2)[:50000])
        synthesis_prompt = synthesis_prompt.replace("{web_context}", json.dumps(web_context, ensure_ascii=False, indent=2)[:50000])
        prompt = SYSTEM_PROMPT + "\n\n" + synthesis_prompt
        response = self._generate(
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.05, response_mime_type="application/json"),
            operation="síntese das regras",
        )
        data = safe_json_loads(response.text)
        if isinstance(data, dict):
            data["_model_used"] = self.last_model_used
        return data

    def generate_scenarios(self, objective: str, priority: str, rules: Dict[str, Any], calculations: Dict[str, Any]) -> List[Dict[str, Any]]:
        scenario_prompt = SCENARIO_PROMPT
        scenario_prompt = scenario_prompt.replace("{objective}", str(objective))
        scenario_prompt = scenario_prompt.replace("{priority}", str(priority))
        scenario_prompt = scenario_prompt.replace("{rules}", json.dumps(rules, ensure_ascii=False, indent=2))
        scenario_prompt = scenario_prompt.replace("{calculations}", json.dumps(calculations, ensure_ascii=False, indent=2))
        prompt = SYSTEM_PROMPT + "\n\n" + scenario_prompt
        response = self._generate(
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json"),
            operation="geração de cenários",
        )
        data = safe_json_loads(response.text)
        return data.get("scenarios", [])
