from __future__ import annotations
import json, random, time, hashlib
from typing import Any, Dict, List
from urllib.parse import urlparse
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_TIMEOUT_MS
from core.utils import safe_json_loads
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.document_prompt import DOCUMENT_PROMPT
from prompts.scenario_prompt import SCENARIO_PROMPT
from prompts.research_prompt import DIRECT_RESEARCH_PROMPT, DEEP_PARAMETER_PROMPT

class GeminiTemporarilyUnavailable(RuntimeError):
    pass

OFFICIAL_HINTS = (
    "diariodarepublica.pt", "dre.pt", "cm-", ".gov.pt", "dgterritorio", "snit", "ccdr", "apambiente", "icnf",
    "patrimoniocultural", "infraestruturasdeportugal", "mun-", "municipio", "cmaveiro", "cm-gaia", "gaiaurb"
)

class GeminiService:
    def __init__(self, api_key: str = "", model: str = ""):
        key = api_key or GEMINI_API_KEY
        if not key: raise RuntimeError("GEMINI_API_KEY não configurada.")
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        self.model = model or GEMINI_MODEL
        self.models=[]
        for m in [self.model, "gemini-2.5-flash"] + list(GEMINI_FALLBACK_MODELS):
            if m and m not in self.models: self.models.append(m)
        self.last_model_used=None

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        t=str(exc).lower()
        return any(x in t for x in ["503","unavailable","high demand","overloaded","capacity","429","resource_exhausted","rate limit","504","deadline_exceeded","timeout"])

    def _generate(self, *, contents, config, operation="análise", models=None):
        models=models or self.models
        errors=[]
        for model in models:
            for attempt in range(2):
                try:
                    r=self.client.models.generate_content(model=model, contents=contents, config=config)
                    self.last_model_used=model
                    return r
                except Exception as e:
                    errors.append(f"{model}/{attempt+1}: {e}")
                    if not self._is_retryable(e): raise
                    if attempt == 0: time.sleep(0.7 + random.random()*0.5)
            time.sleep(0.4)
        raise GeminiTemporarilyUnavailable(f"O serviço Gemini está temporariamente indisponível para {operation}. Tente novamente dentro de instantes.")

    def analyze_documents(self, uploaded_files) -> Dict[str, Any]:
        contents=[]; manifest=[]
        for f in uploaded_files:
            data=f.getvalue(); mime=getattr(f,"type",None) or "application/pdf"
            manifest.append({"filename":f.name,"mime_type":mime,"size":len(data)})
            contents += [types.Part.from_bytes(data=data,mime_type=mime), f"NOME_DO_FICHEIRO: {f.name}"]
        contents.append(SYSTEM_PROMPT+"\n\n"+DOCUMENT_PROMPT+"\n\nMANIFESTO:\n"+json.dumps(manifest,ensure_ascii=False))
        r=self._generate(contents=contents,config=types.GenerateContentConfig(temperature=0.05,response_mime_type="application/json"),operation="análise documental")
        data=safe_json_loads(r.text)
        if isinstance(data,dict): data["_model_used"]=self.last_model_used
        return data

    def _grounded_json(self, prompt: str, operation: str) -> Dict[str, Any]:
        tool=types.Tool(google_search=types.GoogleSearch())
        # Para pesquisa pública, privilegia 2.5 Flash pela disponibilidade/latência.
        models=[]
        for m in ["gemini-2.5-flash", self.model] + list(GEMINI_FALLBACK_MODELS):
            if m and m not in models: models.append(m)
        r=self._generate(contents=SYSTEM_PROMPT+"\n\n"+prompt,config=types.GenerateContentConfig(temperature=0.01,tools=[tool]),operation=operation,models=models)
        text=r.text or ""
        data=safe_json_loads(text)
        citations=[]; queries=[]
        try:
            gm=r.candidates[0].grounding_metadata
            for ch in gm.grounding_chunks or []:
                if getattr(ch,"web",None):
                    u=ch.web.uri or ""; title=ch.web.title or ""
                    if u and not any(x["url"]==u for x in citations): citations.append({"title":title,"url":u})
            queries=list(gm.web_search_queries or [])
        except Exception: pass
        for i,s in enumerate(citations,1):
            s["ref"]=i; s["label"]=f"[{i}]"; s["official"]=self._official_url(s.get("url",""))
        return {"data":data,"text":text,"citations":citations,"queries":queries,"model_used":self.last_model_used}

    @staticmethod
    def _official_url(url: str) -> bool:
        try: host=urlparse(url).netloc.lower()
        except Exception: host=url.lower()
        return any(h in host for h in OFFICIAL_HINTS)

    @staticmethod
    def _map_refs(rules: Dict[str,Any], citations: List[Dict[str,Any]]):
        """Converte source_urls em referências numéricas e preserva URLs sem correspondência como evidência textual."""
        by_url={str(c.get("url")):c.get("ref") for c in citations if c.get("url")}
        def visit(x):
            if isinstance(x,dict):
                urls=x.get("source_urls")
                if isinstance(urls,list):
                    refs=[]
                    for u in urls:
                        if u in by_url and by_url[u] not in refs: refs.append(by_url[u])
                    x["sources"]=refs
                for v in x.values(): visit(v)
            elif isinstance(x,list):
                for v in x: visit(v)
        visit(rules)
        return rules

    @staticmethod
    def _numeric_coverage(rules: Dict[str,Any]):
        params=(rules or {}).get("parameters",{}) or {}
        keys=["utilization_index","occupation_index","impermeability_index","max_height_m","max_floors_above_ground"]
        return sum(1 for k in keys if isinstance(params.get(k),dict) and params[k].get("value") not in (None,"","None"))

    @staticmethod
    def _merge_parameters(base: Dict[str,Any], extra: Dict[str,Any]):
        bp=base.setdefault("parameters",{})
        for k,v in (extra.get("parameters") or {}).items():
            if not isinstance(v,dict): continue
            current=bp.get(k) if isinstance(bp.get(k),dict) else {}
            # Só substitui quando o aprofundamento acrescenta valor, regra textual, artigo ou melhor confiança.
            better=(v.get("value") not in (None,"","None") or bool(v.get("value_text")) or bool(v.get("article")) or int(v.get("confidence") or 0)>int(current.get("confidence") or 0))
            if better: bp[k]={**current,**v}
        return base

    def research_rules(self, study_context: Dict[str,Any], document_context: Dict[str,Any], force_deep: bool=True) -> Dict[str,Any]:
        p=DIRECT_RESEARCH_PROMPT.replace("{study_context}",json.dumps(study_context,ensure_ascii=False,indent=2))
        p=p.replace("{document_context}",json.dumps(document_context or {},ensure_ascii=False,indent=2)[:48000])
        first=self._grounded_json(p,"pesquisa territorial e regulamentar")
        rules=first.get("data") or {}
        if not isinstance(rules,dict) or rules.get("parse_error"):
            raise RuntimeError("A pesquisa não devolveu uma matriz estruturada válida.")
        citations=list(first.get("citations") or [])
        rules=self._map_refs(rules,citations)

        # Aprofundamento AUTOMÁTICO quando faltam parâmetros-chave, sem exigir um segundo clique ao utilizador.
        if force_deep and self._numeric_coverage(rules) < 2:
            deep_prompt=DEEP_PARAMETER_PROMPT.replace("{current_rules}",json.dumps(rules,ensure_ascii=False,indent=2)[:26000])
            deep_prompt=deep_prompt.replace("{study_context}",json.dumps(study_context,ensure_ascii=False,indent=2))
            try:
                second=self._grounded_json(deep_prompt,"aprofundamento dos parâmetros urbanísticos")
                extra=second.get("data") or {}
                # anexar citações novas e remapear tudo
                for s in second.get("citations") or []:
                    if s.get("url") and not any(c.get("url")==s.get("url") for c in citations):
                        s=dict(s); s["ref"]=len(citations)+1; s["label"]=f"[{len(citations)+1}]"; citations.append(s)
                rules=self._merge_parameters(rules,extra)
                rules=self._map_refs(rules,citations)
                rules.setdefault("research_notes",[]).extend(extra.get("notes") or [])
            except Exception as e:
                rules.setdefault("research_notes",[]).append(f"Aprofundamento automático indisponível: {e}")

        # Normalização determinística — localização e área nunca são inventadas pela IA.
        ident=rules.setdefault("identification",{})
        ident["street_or_place"]=study_context.get("location_text") or ident.get("street_or_place") or ""
        ident["municipality"]=ident.get("municipality") or study_context.get("municipality") or ""
        ident["parish"]=ident.get("parish") or study_context.get("parish") or ""
        ident["district"]=ident.get("district") or study_context.get("district") or ""
        ident["lat"]=study_context.get("lat"); ident["lon"]=study_context.get("lon")
        if study_context.get("confirmed_area_m2"):
            ident["area_m2"]=study_context["confirmed_area_m2"]; ident["area_source"]=study_context.get("confirmed_area_source") or "confirmada pelo utilizador"
        elif study_context.get("estimated_area_m2"):
            ident["area_m2"]=study_context["estimated_area_m2"]; ident["area_source"]="polígono cartográfico"
        else:
            ident["area_m2"]=None

        # inputs determinísticos para cálculo
        ci={"parcel_area_m2":ident.get("area_m2")}
        mapping={"utilization_index":"utilization_index","occupation_index":"occupation_index","impermeability_index":"impermeability_index","max_height_m":"max_height_m","max_floors_above_ground":"max_floors"}
        for src,dst in mapping.items():
            item=(rules.get("parameters") or {}).get(src) or {}
            if isinstance(item,dict) and item.get("value") not in (None,"","None"): ci[dst]=item.get("value")
        rules["calculation_inputs"]=ci

        # confiança global derivada, não escolhida livremente pelo modelo
        planning=rules.get("planning") or {}; numeric=self._numeric_coverage(rules)
        official_refs=sum(1 for c in citations if c.get("official"))
        pconf=int(planning.get("confidence") or 0)
        score=min(98, max(0, int(0.35*pconf + numeric*10 + min(official_refs,5)*5)))
        if not planning.get("instrument"): score=min(score,35)
        if not (planning.get("category") or planning.get("subcategory")): score=min(score,60)
        rules["overall_readiness"]={"score":score,"label":"muito_boa" if score>=85 else "boa" if score>=70 else "condicionada" if score>=45 else "insuficiente","reason":f"{numeric}/5 parâmetros quantitativos principais; {official_refs} fontes oficiais localizadas."}
        rules["_model_used"]=self.last_model_used
        return {"rules":rules,"citations":citations,"queries":first.get("queries") or [],"model_used":self.last_model_used}

    def deepen_missing_parameters(self, study_context: Dict[str,Any], rules: Dict[str,Any]) -> Dict[str,Any]:
        p=DEEP_PARAMETER_PROMPT.replace("{current_rules}",json.dumps(rules,ensure_ascii=False,indent=2)[:28000])
        p=p.replace("{study_context}",json.dumps(study_context,ensure_ascii=False,indent=2))
        second=self._grounded_json(p,"verificação aprofundada dos parâmetros")
        extra=second.get("data") or {}
        merged=self._merge_parameters(dict(rules),extra)
        return {"rules":merged,"citations":second.get("citations") or [],"model_used":second.get("model_used")}

    def generate_scenarios(self, objective: str, priority: str, rules: Dict[str,Any], calculations: Dict[str,Any]) -> List[Dict[str,Any]]:
        p=SCENARIO_PROMPT.replace("{objective}",str(objective)).replace("{priority}",str(priority))
        p=p.replace("{rules}",json.dumps(rules,ensure_ascii=False,indent=2)).replace("{calculations}",json.dumps(calculations,ensure_ascii=False,indent=2))
        r=self._generate(contents=SYSTEM_PROMPT+"\n\n"+p,config=types.GenerateContentConfig(temperature=0.08,response_mime_type="application/json"),operation="geração de cenários")
        data=safe_json_loads(r.text)
        return data.get("scenarios",[]) if isinstance(data,dict) else []
