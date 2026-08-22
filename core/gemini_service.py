from __future__ import annotations
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.api_key = key
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        self.model = model or GEMINI_MODEL
        self.models = []
        # 2.5 Flash é usado como fallback de alta disponibilidade para grounding/pesquisa.
        for m in [self.model, "gemini-2.5-flash"] + list(GEMINI_FALLBACK_MODELS):
            if m and m not in self.models:
                self.models.append(m)
        self.last_model_used = None

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        text = str(exc).lower()
        needles = ["503", "unavailable", "high demand", "overloaded", "capacity", "429", "resource_exhausted", "rate limit", "504", "deadline_exceeded", "timeout"]
        return any(n in text for n in needles)

    def _generate(self, *, contents, config, operation: str = "análise", models: List[str] | None = None):
        models = models or self.models
        errors = []
        for idx, model in enumerate(models):
            try:
                response = self.client.models.generate_content(model=model, contents=contents, config=config)
                self.last_model_used = model
                return response
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                if not self._is_retryable(exc):
                    raise
                if idx < len(models) - 1:
                    time.sleep(min(1.0 + idx * 0.8 + random.random() * 0.5, 3.0))
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

    def _grounded_query(self, prompt: str, operation: str) -> Dict[str, Any]:
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        # Para pesquisa, prefere 2.5 Flash como primeiro fallback estável caso o modelo configurado esteja congestionado.
        search_models = []
        for m in [self.model, "gemini-2.5-flash"] + list(GEMINI_FALLBACK_MODELS):
            if m and m not in search_models:
                search_models.append(m)
        response = self._generate(
            contents=SYSTEM_PROMPT + "\n\n" + prompt,
            config=types.GenerateContentConfig(temperature=0.05, tools=[grounding_tool]),
            operation=operation,
            models=search_models,
        )
        citations = []
        queries = []
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
            pass
        return {"text": response.text or "", "citations": citations, "queries": queries, "model_used": self.last_model_used}

    def web_research(self, study_context: Dict[str, Any], document_context: Dict[str, Any]) -> Dict[str, Any]:
        base = WEB_RESEARCH_PROMPT.replace("{study_context}", json.dumps(study_context, ensure_ascii=False, indent=2))
        base = base.replace("{document_context}", json.dumps(document_context, ensure_ascii=False, indent=2)[:42000])

        # Divide a pesquisa em dois blocos curtos e complementares. Corre em paralelo para reduzir a latência total.
        prompts = {
            "planeamento": base + "\n\nFOCO DESTA CHAMADA: localização administrativa, PDM/IGT, classificação do solo e regras de edificabilidade. Não aprofundes condicionantes que não sejam necessárias para confirmar o instrumento.",
            "condicionantes": base + "\n\nFOCO DESTA CHAMADA: condicionantes/servidões e legislação especial aplicável ao local. Confirma também qualquer PP/PU/medida preventiva que altere o regime do PDM.",
        }
        parts = {}
        errors = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(self._grounded_query, p, f"pesquisa territorial · {name}"): name for name, p in prompts.items()}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    parts[name] = fut.result()
                except Exception as e:
                    errors.append(f"{name}: {e}")

        if not parts:
            raise GeminiTemporarilyUnavailable("Não foi possível concluir a pesquisa territorial em nenhuma das frentes.")

        citations = []
        queries = []
        texts = []
        models = []
        for name in ["planeamento", "condicionantes"]:
            part = parts.get(name)
            if not part:
                continue
            texts.append(f"### {name.upper()}\n{part.get('text','')}")
            queries.extend(part.get("queries") or [])
            if part.get("model_used"):
                models.append(part.get("model_used"))
            for src in part.get("citations") or []:
                if src.get("url") and not any(x.get("url") == src.get("url") for x in citations):
                    citations.append(dict(src))

        for i, src in enumerate(citations, 1):
            src["ref"] = i
            src["label"] = f"[{i}]"

        return {
            "text": "\n\n".join(texts),
            "citations": citations,
            "queries": list(dict.fromkeys(queries)),
            "models_used": list(dict.fromkeys(models)),
            "partial_errors": errors,
        }

    def synthesize_rules(self, study_context: Dict[str, Any], document_context: Dict[str, Any], web_context: Dict[str, Any]) -> Dict[str, Any]:
        synthesis_prompt = SYNTHESIS_PROMPT
        synthesis_prompt = synthesis_prompt.replace("{study_context}", json.dumps(study_context, ensure_ascii=False, indent=2))
        synthesis_prompt = synthesis_prompt.replace("{document_context}", json.dumps(document_context, ensure_ascii=False, indent=2)[:50000])
        synthesis_prompt = synthesis_prompt.replace("{web_context}", json.dumps(web_context, ensure_ascii=False, indent=2)[:52000])
        prompt = SYSTEM_PROMPT + "\n\n" + synthesis_prompt
        response = self._generate(
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.02, response_mime_type="application/json"),
            operation="síntese das regras",
        )
        data = safe_json_loads(response.text)
        if isinstance(data, dict):
            # Normalização determinística: preserva a localização introduzida pelo utilizador
            # e replica parâmetros confirmados para o motor de cálculo.
            ident = data.setdefault("identification", {})
            ident["street_or_place"] = ident.get("street_or_place") or study_context.get("location_text") or ""
            ident["municipality"] = ident.get("municipality") or study_context.get("municipality") or ""
            ident["parish"] = ident.get("parish") or study_context.get("parish") or ""
            if study_context.get("confirmed_area_m2"):
                ident["area_m2"] = study_context.get("confirmed_area_m2")
                ident["area_source"] = study_context.get("confirmed_area_source") or "confirmada pelo utilizador"
            ci = data.setdefault("calculation_inputs", {})
            if study_context.get("confirmed_area_m2"):
                ci["parcel_area_m2"] = study_context.get("confirmed_area_m2")
            params = data.get("parameters") or {}
            mapping = {
                "utilization_index":"utilization_index", "occupation_index":"occupation_index",
                "impermeability_index":"impermeability_index", "max_height_m":"max_height_m",
                "max_floors_above_ground":"max_floors"
            }
            for src,dst in mapping.items():
                item=params.get(src) or {}
                if isinstance(item,dict) and item.get("value") not in (None, "", "None"):
                    ci[dst]=item.get("value")
            # Recalcula um indicador conservador de prontidão; não aceita score otimista sem dados.
            core_keys=["utilization_index","occupation_index","impermeability_index","max_height_m","max_floors_above_ground"]
            have=sum(1 for k in core_keys if isinstance(params.get(k),dict) and params[k].get("value") not in (None,"","None"))
            planning=data.get("planning") or {}
            has_planning=bool(planning.get("instrument") and planning.get("sources"))
            score=min(100, have*15 + (25 if has_planning else 0))
            label="muito_boa" if score>=85 else "boa" if score>=65 else "condicionada" if score>=30 else "insuficiente"
            data["overall_readiness"]={"score":score,"label":label,"reason":f"{have}/5 parâmetros quantitativos principais com valor; instrumento territorial com fonte: {'sim' if has_planning else 'não'}."}
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
            config=types.GenerateContentConfig(temperature=0.12, response_mime_type="application/json"),
            operation="geração de cenários",
        )
        data = safe_json_loads(response.text)
        return data.get("scenarios", []) if isinstance(data, dict) else []
