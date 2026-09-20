"""FastAPI HTTP boundary for the local synthetic research prototype."""
from __future__ import annotations
import copy, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.case import Case
from app.adapters import normalize_case
from app.repositories import SQLiteRepository

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env", override=False)
except ImportError:
    pass
_configured_db_path = Path(os.getenv("PROTOTYPE_DB_PATH", str(ROOT / "data" / "runtime" / "prototype.db")))
if not _configured_db_path.is_absolute():
    _configured_db_path = (ROOT / "backend" / _configured_db_path).resolve()
DB_PATH = _configured_db_path
repo = SQLiteRepository(DB_PATH)
_document_service_instance = None
DISCLAIMER = "研究展示用／病例標示來源與模擬欄位／非臨床使用"
app = FastAPI(title="Antibiotic Prototype API", version="1.0", description=DISCLAIMER)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]
    format: Literal["canonical", "alternate"] = "canonical"
class DocumentPopulationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    population: Literal["unspecified", "all", "adult", "pediatric", "mixed"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_revision: int = Field(ge=0)
class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    mode: Literal["rule-only", "rag-only", "single-agent", "multi-agent"]
    provider_kind: Literal["unconfigured", "mock", "live"] = "unconfigured"
    request_id: str | None = Field(default=None, max_length=200)
    previous_run_id: str | None = None
class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    action: Literal["accept", "modify", "reject"]
    reason: str = Field(min_length=1, max_length=4000)
    reviewer_id: str = Field(min_length=1, max_length=200)
    role: Literal["doctor", "physician", "pharmacist", "research", "researcher", "admin"]
    proposed_output: dict[str, Any] | None = None

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str):
        value=value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value
class BenchmarkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_ids: list[str] = Field(default_factory=list, max_length=100)
    modes: list[Literal["rule-only", "rag-only", "single-agent", "multi-agent"]] = Field(default_factory=lambda: ["rule-only"])
    provider_kind: Literal["unconfigured", "mock", "live"] = "unconfigured"
    request_id: str | None = None
class CaseRecord(BaseModel):
    case_id: str
    revision: int
    case: Case
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
class CaseRevision(CaseRecord):
    created_at: str | None = None

def _engine():
    try:
        from app.workflow import engine
        return engine
    except ImportError: return None
def _documents():
    global _document_service_instance
    try:
        from app.rag.service import DocumentService
        if _document_service_instance is None:
            _document_service_instance=DocumentService(DB_PATH.parent / "documents")
        return _document_service_instance
    except ImportError: return None
def _provider_status(kind: str = "unconfigured"):
    try:
        from app.providers.service import get_provider
        return get_provider(kind).status()
    except Exception:
        configured=bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_MODEL") and os.getenv("LLM_API_KEY"))
        return {"kind":"live" if configured else "unconfigured","model":os.getenv("LLM_MODEL"),"configured":configured,"is_mock":False}

def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    """Remove quarantined baseline model text from normal API/UI responses."""
    public=copy.deepcopy(run)
    # Preserve stored mode and reproducibility; label the retired workflow only
    # for display, so old one-call runs cannot be mistaken for five agents.
    if run.get("mode") == "multi-agent" and run.get("agent_execution") is None:
        public["display_mode"] = "multi-agent-legacy"
    if run.get("agent_execution") is not None or run.get("mode") == "multi-agent-v2":
        from app.workflow.v2 import public_agent_nodes
        public["nodes"] = public_agent_nodes(public.get("nodes", []), publish=bool(public.get("output")) and public.get("gate_status") == "ready_for_review")
    baseline=public.get("raw_baseline")
    if isinstance(baseline,dict):
        baseline.pop("payload",None)
        baseline["withheld"]=True if run.get("mode") != "rule-only" else baseline.get("withheld",False)
    public["disclaimer"]=DISCLAIMER
    return public
def _public_benchmark(obj: dict[str, Any]) -> dict[str, Any]:
    public=copy.deepcopy(obj)
    if isinstance(public.get("results"),list): public["results"]=[_public_run(x) if isinstance(x,dict) else x for x in public["results"]]
    multi = [x for x in public.get("results", []) if isinstance(x, dict) and x.get("mode") == "multi-agent"]
    if multi:
        labels = {x.get("display_mode", "multi-agent") for x in multi}
        public["display_modes"] = {"multi-agent": next(iter(labels)) if len(labels) == 1 else "multi-agent-mixed"}
    return public

@app.on_event("startup")
def startup(): repo.recover_running()
@app.get("/api/health")
def health(): return {"status":"ok"}
@app.get("/api/config")
def config():
    provider_kind=os.getenv("LLM_PROVIDER", "unconfigured").strip().lower() or "unconfigured"
    svc = _documents()
    reference_count = sum(1 for item in svc.list_documents() if not item.get("is_synthetic")) if svc else 0
    reference_status = f"已匯入 {reference_count} 份正式參考文件" if reference_count else "尚未匯入"
    return {"provider":_provider_status(provider_kind),"rag":svc.status(scope='reference') if svc else {"status":"not_configured"},"disclaimer":DISCLAIMER,"rules_status":rules()['status'],"reference_document_count":reference_count,"reference_status":reference_status,"who_status":reference_status}
@app.get("/api/schema")
def schema():
    from app.schemas.case import Case
    return Case.model_json_schema()
@app.get("/api/agents/v2/contracts")
def agent_contracts_v2():
    from app.agents.runtime_v2 import AGENTS, PROMPT_VERSION, COMMON
    return {"version": PROMPT_VERSION, "agents": [
        {"agent_id": agent.id, "depends_on": list(agent.dependencies),
         "system_prompt": COMMON + " " + agent.instruction,
         "input_schema": agent.input_type.model_json_schema(),
         "output_schema": agent.output_type.model_json_schema()} for agent in AGENTS]}
@app.get("/api/cases", response_model=list[CaseRecord])
def list_cases(include_legacy: bool = False):
    records = repo.list_cases()
    if include_legacy or os.getenv('PROTOTYPE_FIXTURE_DIR'):
        return records
    return [r for r in records if not _legacy_case(r['case'])]

def _legacy_case(case):
    return str(case.get('microbiology', {}).get('organism', '')).startswith('DEMO_') or any(str(x.get('drug_code', '')).startswith('DEMO_') for x in case.get('ast_results', []))
@app.post("/api/cases/import")
def import_case(body: ImportBody):
    try: case,warnings=normalize_case(body.payload,body.format)
    except Exception as exc: raise HTTPException(422,detail={"code":"CASE_SCHEMA_INVALID","message":str(exc)})
    return repo.upsert_case(case.model_dump(mode="json"),body.payload,warnings)
@app.get("/api/cases/{case_id}", response_model=CaseRecord)
def case_detail(case_id: str):
    item=repo.get_case(case_id)
    if not item: raise HTTPException(404,"CASE_NOT_FOUND")
    return item
@app.get("/api/cases/{case_id}/revisions", response_model=list[CaseRevision])
def case_revisions(case_id: str): return repo.list_revisions(case_id)
@app.post("/api/cases/{case_id}/revisions")
def create_revision(case_id: str, body: ImportBody):
    if body.payload.get("case_id") != case_id: raise HTTPException(422,"case_id mismatch")
    return import_case(body)

def _fixture_files(): return sorted(Path(os.getenv('PROTOTYPE_FIXTURE_DIR', str(ROOT / 'data/local/microbiology/seeds'))).glob('case-*.json'))
def _seed_payloads():
    if os.getenv('PROTOTYPE_FIXTURE_DIR'):
        return [json.loads(path.read_text(encoding='utf-8')) for path in _fixture_files()]
    path = ROOT / 'data/local/microbiology/cases.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
@app.get("/api/seed-cases")
def seed_cases():
    expectations_path=ROOT / "data" / "synthetic" / "expectations.json"
    expectations=json.loads(expectations_path.read_text(encoding="utf-8")) if expectations_path.exists() else {}
    out=[]
    for payload in _seed_payloads():
        expected=payload.pop("expected",{})
        out.append({"case_id":payload["case_id"],"title":payload['case_id'],"payload":payload,"expected":expected or expectations.get(payload["case_id"],{})})
    return out
@app.post("/api/seed")
def seed():
    count=0
    for payload in _seed_payloads():
        payload.pop("expected",None)
        if not repo.get_case(payload["case_id"]):
            case,warnings=normalize_case(payload); repo.upsert_case(case.model_dump(mode="json"),payload,warnings); count += 1
    # Seed synthetic documents when the document service is present. Hash based
    # deduplication in that service makes this safe to repeat.
    svc=_documents()
    docs_dir=ROOT / "data" / "demo_documents"
    if svc and docs_dir.exists() and os.getenv('PROTOTYPE_FIXTURE_DIR'):
        for path in sorted(docs_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md",".markdown",".txt",".pdf"}:
                if path.name == 'README.md': continue
                try:
                    if path.stem.startswith('conflict_'):
                        svc.import_document(path.name,path.read_bytes(),'SYNTHETIC conflicting policy',path.stem,True,policy_refs=['demo-conflicting-policy'])
                        continue
                    refs=["demo-policy-v1"] if "policy" in path.stem.lower() else []
                    svc.import_document(path.name,path.read_bytes(),path.stem,"demo-v1",True,policy_refs=refs)
                except (ValueError,FileExistsError): pass
    return {"imported":count,"disclaimer":DISCLAIMER,"message":"請先執行本機 CSV 匯入，再載入來源病例；不再載入虛構菌種／藥品。" if not _seed_payloads() else "來源病例已備妥"}

@app.post("/api/runs")
def start_run(body: RunBody):
    item=repo.get_case(body.case_id)
    if not item: raise HTTPException(404,"CASE_NOT_FOUND")
    rid=str(uuid4())
    initial={"run_id":rid,"case_id":body.case_id,"mode":body.mode,"provider_kind":body.provider_kind,"status":"running","created_at":datetime.now(timezone.utc).isoformat(),"demo_only":True}
    if body.mode == "multi-agent":
        initial["agent_execution"] = {"calls": 0}
    existing=repo.create_run(rid,body.case_id,body.mode,body.provider_kind,body.request_id,body.previous_run_id,initial)
    if existing.get("run_id") != rid: return _public_run(existing)
    engine=_engine(); docs=_documents()
    if engine is None:
        result={**initial,"status":"failed","gate_status":"needs_confirmation","errors":[{"code":"WORKFLOW_NOT_AVAILABLE","detail":"workflow engine is not installed"}],"output":None}
    else:
        try:
            def checkpoint(snapshot):
                repo.save_run(rid, {**initial, **snapshot, "case_revision": item["revision"]})
            result=engine.execute(item["case"],body.mode,body.provider_kind,docs,rid,checkpoint=checkpoint)
        except Exception:
            result={**(repo.get_run(rid) or initial),"status":"failed","gate_status":"blocked","output":None,"errors":[{"code":"WORKFLOW_FAILED","detail":"工作流執行失敗，請查看已保存的節點狀態"}]}
    # Every run is an immutable snapshot of the case revision used to produce it.
    result={**initial, **result, "case_revision":item["revision"], "case_snapshot":item["case"], "provider_kind":body.provider_kind, "mode":body.mode, "disclaimer":DISCLAIMER, "demo_only":True}
    return _public_run(repo.save_run(rid,result))
@app.get("/api/runs")
def list_runs(case_id: str | None = None): return [_public_run(x) for x in repo.list_runs(case_id)]
@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run=repo.get_run(run_id)
    if not run: raise HTTPException(404,"RUN_NOT_FOUND")
    return _public_run(run)
@app.get("/api/runs/{run_id}/trace")
def trace(run_id: str):
    run=repo.get_run(run_id)
    if not run: raise HTTPException(404,"RUN_NOT_FOUND")
    return {"run_id":run_id,"nodes":_public_run(run).get("nodes",[]),"disclaimer":DISCLAIMER}
@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str):
    run=repo.get_run(run_id)
    if not run: raise HTTPException(404,"RUN_NOT_FOUND")
    return Response(content=json.dumps(_public_run(run),ensure_ascii=False),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{run_id}.json"'})

@app.get("/api/documents")
def documents():
    svc=_documents()
    return svc.list_documents() if svc else []
@app.post("/api/documents/import")
async def import_document(file: UploadFile = File(...), title: str = Form(""), version: str = Form(""), is_synthetic: bool = Form(True), population: Literal["unspecified", "all", "adult", "pediatric", "mixed"] = Form("unspecified")):
    if not file.filename or Path(file.filename).name != file.filename: raise HTTPException(400,"unsafe filename")
    if Path(file.filename).suffix.lower() not in {".pdf",".md",".markdown",".txt"}: raise HTTPException(422,"unsupported file format")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,"file too large")
    svc=_documents()
    if svc is None: raise HTTPException(503,"DOCUMENT_SERVICE_NOT_AVAILABLE")
    try: return svc.import_document(file.filename,content,title or file.filename,version or "unversioned",is_synthetic,population=population)
    except ValueError as exc: raise HTTPException(422,str(exc))
@app.get("/api/documents/search")
def document_search(q: str = Query(...,min_length=1), limit: int = Query(8,ge=1,le=50), scope: Literal["synthetic", "reference"] = Query("synthetic")):
    svc=_documents()
    if svc is None: return {"status":"not_configured","evidence":[],"warnings":["document service unavailable"],"scope":scope}
    try: return svc.search(q,limit,scope=scope)
    except ValueError as exc: raise HTTPException(422,str(exc))
@app.post("/api/documents/{doc_id}/population")
def update_document_population(doc_id: str, body: DocumentPopulationBody):
    svc = _documents()
    if svc is None: raise HTTPException(503, "DOCUMENT_SERVICE_NOT_AVAILABLE")
    try:
        return svc.update_population(doc_id, body.population, body.reason, body.expected_revision)
    except ValueError as exc:
        code = getattr(exc, "code", "")
        status = 404 if code == "DOCUMENT_NOT_FOUND" else 409 if code == "POPULATION_REVISION_CONFLICT" else 422
        raise HTTPException(status, detail={"code": code, "message": str(exc)})
@app.post("/api/documents/reindex")
def document_reindex(scope: Literal["synthetic", "reference"] = Query("synthetic")):
    svc = _documents()
    if svc is None: raise HTTPException(503,"DOCUMENT_SERVICE_NOT_AVAILABLE")
    try: return svc.reindex(scope=scope)
    except ValueError as exc: raise HTTPException(422,str(exc))
@app.get("/api/documents/{doc_id}")
def document_detail(doc_id: str):
    svc=_documents()
    try: item=svc.detail(doc_id) if svc else None
    except Exception: item=None
    if not item: raise HTTPException(404,"DOCUMENT_NOT_FOUND")
    return item
@app.get("/api/documents/{doc_id}/source")
def document_source(doc_id: str):
    svc=_documents()
    if not svc: raise HTTPException(503,"DOCUMENT_SERVICE_NOT_AVAILABLE")
    try: path,mime=svc.source(doc_id); return Response(content=path.read_bytes(),media_type=mime)
    except Exception: raise HTTPException(404,"DOCUMENT_NOT_FOUND")

@app.delete('/api/documents/{doc_id}')
def delete_document(doc_id: str):
    svc = _documents()
    if svc is None: raise HTTPException(503, 'DOCUMENT_SERVICE_NOT_AVAILABLE')
    try:
        result = svc.delete_document(doc_id)
        return {**result, 'message': '文件與檢索索引已刪除。歷史證據快照保留，原始文件連結不再可用；病例引用不會自動改成 WHO。'}
    except ValueError as exc:
        code = getattr(exc, 'code', 'DOCUMENT_DELETE_FAILED')
        raise HTTPException(404 if code == 'DOCUMENT_NOT_FOUND' else 422, detail={'code': code, 'message': str(exc)})
    except OSError:
        raise HTTPException(409, detail={'code': 'SOURCE_DELETE_FAILED', 'message': '無法刪除原始檔，請關閉佔用檔案的程式後重試。'})

def _reject_forbidden(value: Any):
    forbidden=("dose","frequency","duration","dosage","給藥")
    if isinstance(value,dict):
        for k,v in value.items():
            if any(x in k.lower() for x in forbidden): raise ValueError("prescription fields are forbidden")
            _reject_forbidden(v)
    elif isinstance(value,list):
        for x in value: _reject_forbidden(x)
@app.post("/api/reviews")
def create_review(body: ReviewBody):
    run=repo.get_run(body.run_id)
    if not run: raise HTTPException(404,"RUN_NOT_FOUND")
    # Accept always reviews the stored run output.  Only modify may provide a
    # replacement, and an explicit empty object must not silently fall back.
    proposed=run.get("output") if body.action == "accept" else body.proposed_output
    if body.action in {"modify", "accept"}:
        if proposed is None: raise HTTPException(422,"run has no output to review" if body.action == "accept" else "proposed_output required")
        engine=_engine()
        validated_output=proposed
        try:
            if engine: validated_output=engine.validate_review(run,proposed).get("output", proposed)
            _reject_forbidden(proposed)
        except ValueError as exc: raise HTTPException(422,detail={"code":"REVIEW_OUTPUT_INVALID","message":"審閱內容未通過安全驗證"})
    else:
        validated_output=None
    review={"review_id":str(uuid4()),"run_id":body.run_id,"action":body.action,"reason":body.reason,"reviewer_id":body.reviewer_id,"role":body.role,"original_output":run.get("output"),"new_output":validated_output if body.action=="modify" else None,"created_at":datetime.now(timezone.utc).isoformat(),"disclaimer":DISCLAIMER}
    return repo.add_review(review["review_id"],body.run_id,body.action,review)
@app.get("/api/reviews")
def reviews(run_id: str | None = None): return repo.list_reviews(run_id)
@app.get("/api/rules")
def rules():
    try:
        from app.rules.engine import RuleEngine
        engine=RuleEngine()
        return {"status":engine.config.get("status","demo_only"),"version":engine.version,"config":engine.snapshot()}
    except (ImportError,AttributeError): return {"status":"demo_only","version":"unconfigured","rules":[]}

@app.post("/api/benchmarks")
def benchmark(body: BenchmarkBody):
    cases=body.case_ids or [x["case_id"] for x in list_cases()]
    if body.request_id:
        for old in repo.list_benchmarks():
            if old.get("request_id") == body.request_id: return _public_benchmark(old)
    # Pin every input before the first mode executes; later case revisions must
    # never silently alter a benchmark's comparison set.
    case_inputs={cid:repo.get_case(cid) for cid in cases}
    if any(item is None for item in case_inputs.values()):
        raise HTTPException(404, 'CASE_NOT_FOUND')
    from app.rules.engine import RuleEngine
    pinned_rules=RuleEngine().snapshot()
    documents_service=_documents()
    frozen_evidence={}
    for cid, item in case_inputs.items():
        case=item['case']
        from app.workflow.engine import evidence_query
        query=evidence_query(case)
        scope_kwargs={'scope':'reference'} if case.get('evidence_scope') == 'reference' else {}
        frozen_evidence[cid]=documents_service.search(query or 'synthetic',policy_refs=case.get('policy_refs'), **scope_kwargs) if documents_service else {'status':'not_configured','evidence':[],'warnings':[]}
    class FrozenDocuments:
        def __init__(self, result): self.result=copy.deepcopy(result)
        def search(self, *args, **kwargs): return copy.deepcopy(self.result)
    results=[]
    for cid in cases:
        for mode in body.modes:
            item=case_inputs.get(cid)
            if not item: continue
            rid=str(uuid4()); engine=_engine()
            if engine:
                try: result=engine.execute(item["case"],mode,body.provider_kind,FrozenDocuments(frozen_evidence[cid]),rid,rules_snapshot=pinned_rules)
                except Exception: result={"run_id":rid,"case_id":cid,"mode":mode,"status":"failed","errors":[{"code":"BENCHMARK_FAILED","detail":"benchmark workflow failed"}]}
            else: result={"run_id":rid,"case_id":cid,"mode":mode,"status":"not_configured"}
            if mode == "multi-agent":
                result.setdefault("agent_execution", {"calls": 0})
            result={**result,"case_revision":item["revision"],"case_snapshot":item["case"],"provider_kind":body.provider_kind,"mode":mode,"demo_only":True,"disclaimer":DISCLAIMER,"is_mock":bool(result.get("is_mock", body.provider_kind=="mock"))}
            repo.create_run(rid,cid,mode,body.provider_kind,None,None,result); repo.save_run(rid,result); results.append(result)
    try:
        from app.workflow.benchmark import summarize
        expectations_path=ROOT / "data" / "synthetic" / "expectations.json"
        expectations=json.loads(expectations_path.read_text(encoding="utf-8")) if expectations_path.exists() else {}
        labelled={}
        for fixture in seed_cases():
            cid=fixture['case_id']
            item=case_inputs.get(cid)
            if item and Case.model_validate(fixture['payload']).model_dump(mode='json') == item['case']:
                labelled[cid]=expectations.get(cid,{})
        summary=summarize(results,labelled)
    except Exception: summary={"n":len(results),"metrics":{},"status":"not_evaluated"}
    obj={"benchmark_id":str(uuid4()),"request_id":body.request_id,"cases":cases,"modes":body.modes,"provider_kind":body.provider_kind,"is_mock":body.provider_kind=="mock","results":results,"summary":summary,"seed":"synthetic-v1","created_at":datetime.now(timezone.utc).isoformat(),"disclaimer":DISCLAIMER}
    repo.save_benchmark(obj["benchmark_id"],body.request_id,obj,results)
    return _public_benchmark(obj)
@app.get("/api/benchmarks")
def benchmarks(): return [_public_benchmark(x) for x in repo.list_benchmarks()]
@app.get("/api/benchmarks/{benchmark_id}")
def benchmark_detail(benchmark_id: str):
    item=repo.get_benchmark(benchmark_id)
    if not item: raise HTTPException(404,"BENCHMARK_NOT_FOUND")
    return _public_benchmark(item)
@app.get("/api/benchmarks/{benchmark_id}/export")
def benchmark_export(benchmark_id: str):
    item=repo.get_benchmark(benchmark_id)
    if not item: raise HTTPException(404,"BENCHMARK_NOT_FOUND")
    return JSONResponse(_public_benchmark(item),headers={"Content-Disposition":f'attachment; filename="{benchmark_id}.json"'})
