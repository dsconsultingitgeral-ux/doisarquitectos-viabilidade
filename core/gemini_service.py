from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY, GEMINI_MODEL
from core.utils import safe_json_loads
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.document_prompt import DOCUMENT_PROMPT
from prompts.web_prompt import WEB_RESEARCH_PROMPT
from prompts.synthesis_prompt import SYNTHESIS_PROMPT
from prompts.scenario_prompt import SCENARIO_PROMPT

class GeminiService:
    def __init__(self, api_key: str = "", model: str = ""):
        key = api_key or GEMINI_API_KEY
        if not key:
            raise RuntimeError("GEMINI_API_KEY não configurada.")
        self.client = genai.Client(api_key=key)
        self.model = model or GEMINI_MODEL

    def analyze_documents(self, uploaded_files) -> Dict[str, Any]:
        contents = []
        manifest = []
        for f in uploaded_files:
            data = f.getvalue()
            mime = getattr(f, "type", None) or "application/pdf"
            manifest.append({"filename": f.name, "mime_type": mime, "size": len(data)})
            # Gemini inline PDF/document analysis. For large files, app can later migrate to Files API.
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
            contents.append(f"NOME_DO_FICHEIRO: {f.name}")
        prompt = SYSTEM_PROMPT + "\n\n" + DOCUMENT_PROMPT + "\n\nMANIFESTO:\n" + json.dumps(manifest, ensure_ascii=False)
        contents.append(prompt)
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        return safe_json_loads(response.text)

    def web_research(self, study_context: Dict[str, Any], document_context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = SYSTEM_PROMPT + "\n\n" + WEB_RESEARCH_PROMPT.format(
            study_context=json.dumps(study_context, ensure_ascii=False, indent=2),
            document_context=json.dumps(document_context, ensure_ascii=False, indent=2)[:45000],
        )
        # GenerateContent is used because it exposes grounded search metadata and is stable with google-genai.
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, tools=[grounding_tool]),
        )
        citations = []
        try:
            gm = response.candidates[0].grounding_metadata
            for ch in (gm.grounding_chunks or []):
                if getattr(ch, "web", None):
                    citations.append({"title": ch.web.title or "", "url": ch.web.uri or ""})
            queries = list(gm.web_search_queries or [])
        except Exception:
            queries = []
        return {"text": response.text or "", "citations": citations, "queries": queries}

    def synthesize_rules(self, study_context: Dict[str, Any], document_context: Dict[str, Any], web_context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = SYSTEM_PROMPT + "\n\n" + SYNTHESIS_PROMPT.format(
            study_context=json.dumps(study_context, ensure_ascii=False, indent=2),
            document_context=json.dumps(document_context, ensure_ascii=False, indent=2)[:50000],
            web_context=json.dumps(web_context, ensure_ascii=False, indent=2)[:50000],
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.05, response_mime_type="application/json"),
        )
        return safe_json_loads(response.text)

    def generate_scenarios(self, objective: str, priority: str, rules: Dict[str, Any], calculations: Dict[str, Any]) -> List[Dict[str, Any]]:
        prompt = SYSTEM_PROMPT + "\n\n" + SCENARIO_PROMPT.format(
            objective=objective, priority=priority,
            rules=json.dumps(rules, ensure_ascii=False, indent=2),
            calculations=json.dumps(calculations, ensure_ascii=False, indent=2),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json"),
        )
        data = safe_json_loads(response.text)
        return data.get("scenarios", [])
