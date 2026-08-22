from __future__ import annotations
import json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from google import genai
from google.genai import types
from .config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_TIMEOUT_MS
from .utils import safe_json_loads
from .prompts import DOCUMENT_PROMPT, PLANNING_PROMPT, PARAMETERS_PROMPT, USES_PROMPT, CONSTRAINTS_PROMPT, POTENTIAL_PROMPT

OFFICIAL_HINTS=(".gov.pt","diariodarepublica.pt","dre.pt","cm-","municipio","snit","dgterritorio","dgt","ccdr","apambiente","icnf","dgadr","patrimoniocultural","infraestruturasdeportugal","ip.pt")

class UrbanEngine:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY não configurada nos Secrets.")
        self.client=genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        self.models=[]
        for m in [GEMINI_MODEL]+GEMINI_FALLBACK_MODELS:
            if m and m not in self.models:self.models.append(m)
        self.last_model=None

    def _generate(self, contents, config, operation="IA"):
        errors=[]
        for model in self.models:
            for attempt in range(2):
                try:
                    r=self.client.models.generate_content(model=model,contents=contents,config=config)
                    self.last_model=model
                    return r
                except Exception as e:
                    msg=str(e); errors.append(f"{model}: {msg}")
                    if "404" in msg or "NOT_FOUND" in msg: break
                    if any(x in msg for x in ["429","500","502","503","504","UNAVAILABLE","RESOURCE_EXHAUSTED","timeout","Timeout"]):
                        time.sleep(1.5*(attempt+1)); continue
                    break
        raise RuntimeError(f"Não foi possível concluir {operation}. O serviço de IA não respondeu de forma utilizável.")

    def _repair_json(self, raw_text: str, expected_group: str):
        prompt=f"Converte a resposta abaixo em JSON válido. Não alteres o conteúdo factual. O campo group deve ser '{expected_group}'. Responde só JSON.\n\n{raw_text[:30000]}"
        r=self._generate(prompt,types.GenerateContentConfig(temperature=0,response_mime_type="application/json"),"reparação de resposta")
        return safe_json_loads(r.text or "")

    def analyze_documents(self, files):
        if not files:return {"documents":[],"combined":{}}
        parts=[]
        for f in files:
            data=f.getvalue(); mime=getattr(f,"type",None) or "application/pdf"
            parts.append(types.Part.from_bytes(data=data,mime_type=mime)); parts.append(f"NOME_DO_FICHEIRO: {f.name}")
        parts.append(DOCUMENT_PROMPT)
        r=self._generate(parts,types.GenerateContentConfig(temperature=0.02,response_mime_type="application/json"),"análise documental")
        data=safe_json_loads(r.text or "") or {"documents":[],"combined":{}}
        data["_model_used"]=self.last_model
        return data

    @staticmethod
    def _official(url):
        try: host=urlparse(url).netloc.lower()
        except Exception: host=str(url).lower()
        return any(h in host for h in OFFICIAL_HINTS)

    def _research_group(self, prompt_template: str, group: str, context: dict):
        prompt=prompt_template+"\n\nCONTEXTO DO TERRENO E DOCUMENTOS:\n"+json.dumps(context,ensure_ascii=False,indent=2)[:50000]
        tool=types.Tool(google_search=types.GoogleSearch())
        r=self._generate(prompt,types.GenerateContentConfig(temperature=0.01,tools=[tool]),f"pesquisa {group}")
        data=safe_json_loads(r.text or "")
        if not isinstance(data,dict) or data.get("group")!=group:
            data=self._repair_json(r.text or "",group)
        if not isinstance(data,dict):
            data={"group":group,"items":{},"notes":["Resposta não estruturada; grupo não concluído."]}
        citations=[]
        try:
            gm=r.candidates[0].grounding_metadata
            for ch in gm.grounding_chunks or []:
                if getattr(ch,"web",None):
                    u=ch.web.uri or ""; t=ch.web.title or ""
                    if u and not any(c["url"]==u for c in citations): citations.append({"url":u,"title":t,"official":self._official(u)})
        except Exception:pass
        return data,citations

    def research(self, context: dict, progress_cb=None):
        groups=[("planning",PLANNING_PROMPT),("parameters",PARAMETERS_PROMPT),("uses",USES_PROMPT),("constraints",CONSTRAINTS_PROMPT)]
        result={"planning":{},"parameters":{},"uses":{},"constraints":{},"notes":[],"sources":[]}
        completed=0
        # As quatro checklists são independentes; executá-las em paralelo reduz a espera total.
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures={ex.submit(self._research_group,prompt,name,context):name for name,prompt in groups}
            for fut in as_completed(futures):
                name=futures[fut]; completed+=1
                if progress_cb: progress_cb(completed,len(groups),name)
                try:
                    data,cites=fut.result()
                    result[name]=data.get("items") or {}
                    result["notes"].extend(data.get("notes") or [])
                    for c in cites:
                        if c["url"] not in [s["url"] for s in result["sources"]]:result["sources"].append(c)
                except Exception as e:
                    result["notes"].append(f"Grupo {name} indisponível: {e}")
        for i,s in enumerate(result["sources"],1):s["ref"]=i
        # map source URLs to refs per item
        by={s["url"]:s["ref"] for s in result["sources"]}
        for group in ["planning","parameters","uses","constraints"]:
            for item in (result[group] or {}).values():
                if isinstance(item,dict):
                    item["refs"]=[by[u] for u in item.get("source_urls",[]) if u in by]
        return result

    def potential(self, context: dict, research: dict, calculations: dict):
        payload={"context":context,"research":research,"calculations":calculations}
        prompt=POTENTIAL_PROMPT+"\n\nDADOS:\n"+json.dumps(payload,ensure_ascii=False,indent=2)[:50000]
        r=self._generate(prompt,types.GenerateContentConfig(temperature=0.04,response_mime_type="application/json"),"síntese de potencial")
        return safe_json_loads(r.text or "") or {}
