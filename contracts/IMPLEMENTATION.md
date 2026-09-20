# Integration contract v1

Root: Python FastAPI backend (run from backend, app.main:app), React/TS/Vite frontend port 5173. API prefix /api. Local SQLite with versioned migrations. All JSON responses and UI carry research/synthetic disclaimer. No real medical rules.

## Ownership
- Backend agent: backend/app/main.py, schemas/, repositories/, adapters/, backend tests for these, requirements.txt, scripts/, data/synthetic/, contracts generated schemas.
- Workflow agent: backend/app/workflow/, rules/, agents/, configs/demo/, backend/tests/test_workflow.py, benchmark logic in workflow/benchmark.py.
- RAG/provider agent: backend/app/rag/, providers/, backend/tests/test_rag.py and test_providers.py, data/demo_documents/.
- Root: frontend/, docs/, README, integration fixes after coordination.

## Python module interfaces (plain JSON dictionaries at boundaries)
- app.schemas.case.Case: Pydantic v2 case model, normalized case dict has case_id,schema_version,is_synthetic,source,created_at,demographics,encounter,renal,allergies,microbiology,ast_results,rapid_identification,medications,resistance_context_ref,policy_refs,provenance. Nested fields use explicit drug_code, organism, standard, standard_version, mic, comparator, unit, reported_sir. Renal uses egfr and unit; allergies {status,items:[{drug_code,reaction,severity}]}. Unknown nullable; extras forbidden, timestamps aware.
- app.rag.service.DocumentService(storage_dir: Path): import_document(filename:str, content:bytes, title:str, version:str, is_synthetic:bool=True) -> dict; list_documents()->list[dict]; search(query:str, limit:int=8, policy_refs:list[str]|None=None)->dict {status,evidence:[{chunk_id,doc_id,document_version,text,location,...}],warnings:[]}; source(doc_id:str)-> tuple[Path,str]; detail(doc_id:str)->dict. Service owns its document SQLite DB. Search only synthetic eligible evidence, filter policy_refs if supplied. Retain immutable versions/hash.
- app.providers.service.get_provider(kind:str='unconfigured')->provider; provider.status()->dict; provider.generate(context:dict)->dict {output:{candidates:[{drug_code,reason,rule_refs:[],evidence_refs:[]}],avoid:[],limitations:[]},usage:null|dict,model:str,is_mock:bool,retries:int}. ProviderError(code) sanitized. kind live uses env config; mock only explicit. Provider receives mode, case summary, allowed_drugs, evidence, rule_refs. Workflow validates every output (provider adapter also schema validation).
- app.workflow.engine.execute(case:dict, mode:str, provider_kind:str, document_service, run_id:str)->dict. Modes rule-only,rag-only,single-agent,multi-agent. Returns run_id,status,mode,is_mock,gate_status,output,raw_baseline (quarantined),nodes,rule_evaluations,evidence_snapshots,versions,errors,missing_fields,usage,elapsed_ms. output candidates/avoid/limitations plus run_id,demo_only,gate_status. Unknown model => not_configured/partial, rule-only usable. Baseline trace has eight nodes; multi-agent adds five independent agent calls between preflight and final presentation. The retired one-call multi-agent is no longer executable; historical run modes remain unchanged. app.workflow.engine.validate_review(run:dict, proposed:dict)->dict (raises ValueError on forbidden modification). Rules versioned synthetic config only.
- app.workflow.benchmark.summarize(results:list[dict], expectations:dict)->dict with denominators and null N/A, no invented values. Backend creates/persists benchmark runs and invokes same execute modes.

## API JSON contracts
- GET /health -> {status}; GET /config -> {provider:dict,disclaimer,rules_status,who_status}; GET /schema -> Case JSON schema
- GET /cases -> list of {case_id,revision,case:dict,warnings:[]}; POST /cases/import body {payload:dict,format:'canonical'|'alternate'} -> same; GET /cases/{id} -> same; GET /cases/{id}/revisions -> list; POST /cases/{id}/revisions body same import wrapper.
- GET /seed-cases -> list of {case_id,title,payload,expected}; POST /seed -> {imported:int} idempotent seeds cases and synthetic documents.
- POST /runs body {case_id,mode,provider_kind:'unconfigured'|'mock'|'live',request_id,previous_run_id?:str} -> run dict; GET /runs?case_id= -> list; GET /runs/{id} -> run; GET /runs/{id}/trace -> nodes; GET /runs/{id}/export -> JSON attachment. Synchronous bounded execution acceptable with running persisted before execution; API UI loading. request_id idempotent.
- GET /documents -> list; POST /documents/import multipart file,title,version,is_synthetic -> doc; GET /documents/search?q=... -> search dict; GET /documents/{id} -> detail; GET /documents/{id}/source -> file.
- POST /reviews body {run_id,action:'accept'|'modify'|'reject',reason,reviewer_id,role,proposed_output?:dict} -> review; GET /reviews?run_id= -> list. Must revalidate and persist original/new content.
- GET /rules -> versioned config
- POST /benchmarks body {case_ids:[],modes:[],provider_kind,request_id} -> {benchmark_id,results,summary,...}; GET /benchmarks -> list; GET /benchmarks/{id} -> detail; GET /benchmarks/{id}/export -> JSON.

Errors HTTP 422 field validation; safe detail string/object for other errors. No secrets in logs/errors/exports. UI renders baseline only as withheld metadata, never raw risky text. No paid calls without live choice.

## Embedding retrieval extension

- `DocumentService` defaults to `RAG_RETRIEVAL_MODE=embedding`, using Ollama. `retrieval_mode="lexical"` is an explicit offline comparison/test option.
- `status()` returns non-sensitive configuration and local vector counts; it does not probe connectivity.
- `reindex()` rebuilds eligible synthetic chunk vectors for the selected provider identity. `POST /api/documents/reindex` exposes this operation; failures return `status=failed` with safe warnings.
- `GET /api/config` includes `rag`. Search results include `retrieval_method`, `embedding_model`, and cosine `score` on embedding evidence. Existing chunk IDs, locations and source references remain unchanged.
- Embedding setup is independent of answer-generation provider choice. The default endpoint is local; explicitly configuring a remote embedding endpoint sends eligible synthetic chunks and queries there.
