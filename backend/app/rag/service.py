"""Synthetic-document ingestion and retrieval service.

Embedding retrieval is the production default.  Lexical retrieval remains
available only when explicitly selected (for deterministic offline fixtures).
The service does not turn document text into clinical rules and keeps every
imported version and original file so old run evidence remains reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, Sequence


class EmbeddingError(RuntimeError):
    """An embedding provider failed or returned an unsafe result."""


class EmbeddingProvider(Protocol):
    """Replaceable boundary for local or test embedding providers."""

    provider: str
    model: str
    base_url: str
    prompt_version: str

    def embed(self, inputs: Sequence[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    """Adapter for Ollama's ``POST /api/embed`` endpoint.

    The adapter intentionally performs no fallback.  An unavailable Ollama
    server is reported to the retrieval boundary, which then returns no
    evidence so the workflow safety gate can block.
    """

    provider = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "embeddinggemma",
        timeout: float = 30.0,
        prompt_version: str | None = None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.model = str(model)
        self.timeout = float(timeout)
        is_embeddinggemma = self.model.casefold().split(":", 1)[0] == "embeddinggemma"
        self.prompt_version = str(prompt_version or ("embeddinggemma-task-v1" if is_embeddinggemma else _EMBEDDING_PROMPT_VERSION))

    def _prepare(self, inputs: Sequence[str], purpose: str) -> list[str]:
        if self.model.casefold().split(":", 1)[0] != "embeddinggemma":
            return list(inputs)
        if purpose == "query":
            return [f"task: search result | query: {text}" for text in inputs]
        return [f"title: none | text: {text}" for text in inputs]

    def embed(self, inputs: Sequence[str]) -> list[list[float]]:
        try:
            import httpx

            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": list(inputs), "truncate": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise EmbeddingError("embedding provider unavailable") from exc
        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list):
            raise EmbeddingError("embedding provider returned an invalid response")
        return vectors

    def embed_query(self, query: str) -> list[list[float]]:
        return self.embed(self._prepare([query], "query"))

    def embed_documents(self, documents: Sequence[str]) -> list[list[float]]:
        return self.embed(self._prepare(documents, "document"))


# Friendly aliases for callers that use either terminology.
OllamaEmbeddingAdapter = OllamaEmbeddingProvider


class DocumentServiceError(ValueError):
    """A safe, user-facing document service error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class Retriever(Protocol):
    """Replaceable retrieval boundary used by the workflow."""

    def search(self, query: str, limit: int = 8, policy_refs: list[str] | None = None, *, scope: str = "synthetic") -> dict[str, Any]: ...


_ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}
_MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
_MAX_CHUNK_CHARS = 1400
_OVERLAP_CHARS = 160
_EMBEDDING_PROMPT_VERSION = "rag-embedding-v1"
_EMBEDDING_BATCH_SIZE = 32
_DOCUMENT_SCOPES = {"synthetic", "reference"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _safe_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise DocumentServiceError("INVALID_FILENAME", "檔名不可為空白")
    # A client supplies a filename, never a path.  This catches both slash
    # conventions on Windows and POSIX, including drive-qualified paths.
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise DocumentServiceError("INVALID_FILENAME", "檔名不得包含路徑")
    if filename in {".", ".."} or "\x00" in filename:
        raise DocumentServiceError("INVALID_FILENAME", "檔名不安全")
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise DocumentServiceError("UNSUPPORTED_FORMAT", "僅支援 PDF、TXT 與 Markdown 文件")
    return filename


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


class DocumentService:
    """Import, index, search and inspect local demo documents.

    ``storage_dir`` is the sole write boundary.  The service never opens a
    path supplied by a caller; original files are named from generated IDs.
    """

    def __init__(
        self,
        storage_dir: Path,
        *,
        max_document_bytes: int = _MAX_DOCUMENT_BYTES,
        embedding_provider: EmbeddingProvider | Any | None = None,
        retrieval_mode: str | None = None,
        embedding_model: str | None = None,
        embedding_base_url: str | None = None,
        embedding_timeout: float | None = None,
        embedding_prompt_version: str | None = None,
    ):
        self.storage_dir = Path(storage_dir).expanduser().resolve()
        self.max_document_bytes = max_document_bytes
        # Environment configuration is deliberately read at construction so
        # applications can configure each service instance independently.
        import os
        self._configuration_warnings: list[str] = []
        self.retrieval_mode = (retrieval_mode or os.getenv("RAG_RETRIEVAL_MODE", "embedding")).strip().lower()
        if self.retrieval_mode not in {"embedding", "lexical"}:
            self._configuration_warnings.append("invalid_retrieval_mode_defaulted")
            self.retrieval_mode = "embedding"
        try:
            configured_timeout = float(embedding_timeout if embedding_timeout is not None else os.getenv("EMBEDDING_TIMEOUT", os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30")))
        except (TypeError, ValueError):
            configured_timeout = 30.0
            self._configuration_warnings.append("invalid_embedding_timeout_defaulted")
        if not math.isfinite(configured_timeout) or configured_timeout <= 0:
            configured_timeout = 30.0
            self._configuration_warnings.append("invalid_embedding_timeout_defaulted")
        self.embedding_provider = embedding_provider or OllamaEmbeddingProvider(
            base_url=embedding_base_url or os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:11434"),
            model=embedding_model or os.getenv("EMBEDDING_MODEL", "embeddinggemma"),
            timeout=configured_timeout,
            prompt_version=embedding_prompt_version,
        )
        self.originals_dir = self.storage_dir / "originals"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "rag.sqlite3"
        self._init_db()

    @contextmanager
    def _connect(self):
        """Yield one connection and always close it after commit/rollback."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                  doc_id TEXT PRIMARY KEY,
                  document_version TEXT NOT NULL,
                  title TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  source_type TEXT NOT NULL,
                  is_synthetic INTEGER NOT NULL,
                  content_hash TEXT NOT NULL UNIQUE,
                  imported_at TEXT NOT NULL,
                  processing_status TEXT NOT NULL,
                  processing_warnings TEXT NOT NULL,
                  source_path TEXT NOT NULL,
                  metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS chunks (
                  chunk_id TEXT PRIMARY KEY,
                  doc_id TEXT NOT NULL REFERENCES documents(doc_id),
                  document_version TEXT NOT NULL,
                  text TEXT NOT NULL,
                  location TEXT NOT NULL,
                  parse_warnings TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id),
                  fingerprint TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  base_url TEXT NOT NULL,
                  prompt_version TEXT NOT NULL,
                  dimensions INTEGER NOT NULL,
                  vector_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY (chunk_id, fingerprint)
                );
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_fingerprint
                  ON chunk_embeddings(fingerprint);
                """
            )
            try:
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, doc_id UNINDEXED, text)")
                self._fts_available = True
            except sqlite3.OperationalError:
                # Some embedded Python builds omit FTS5.  Keep the same table
                # shape and use the deterministic keyword fallback below.
                db.execute("CREATE TABLE IF NOT EXISTS chunks_fts (chunk_id TEXT, doc_id TEXT, text TEXT)")
                self._fts_available = False

    def import_document(
        self,
        filename: str,
        content: bytes,
        title: str,
        version: str,
        is_synthetic: bool = True,
        *,
        policy_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        filename = _safe_filename(filename)
        if not isinstance(content, (bytes, bytearray)):
            raise DocumentServiceError("INVALID_CONTENT", "文件內容必須是位元組")
        content = bytes(content)
        if len(content) > self.max_document_bytes:
            raise DocumentServiceError("DOCUMENT_TOO_LARGE", "文件超過大小限制")
        if not isinstance(title, str) or not title.strip():
            raise DocumentServiceError("INVALID_TITLE", "文件標題不可為空白")
        if not isinstance(version, str) or not version.strip():
            raise DocumentServiceError("INVALID_VERSION", "文件版本不可為空白")
        if not isinstance(is_synthetic, bool):
            raise DocumentServiceError("INVALID_SYNTHETIC_FLAG", "is_synthetic 必須是布林值")

        digest = hashlib.sha256(content).hexdigest()
        with self._connect() as db:
            existing = db.execute(
                "SELECT * FROM documents WHERE content_hash = ?", (digest,)
            ).fetchone()
            if existing:
                return self._document_row(existing, deduplicated=True)

        doc_id = _new_id("doc")
        suffix = Path(filename).suffix.lower()
        # Parse before writing anything.  In particular, a UTF-8 failure must
        # not leave an orphan upload in the originals directory.
        chunks, warnings, parse_status = self._parse(filename, content, version)
        source_path = self.originals_dir / f"{doc_id}{suffix}"
        # Generated child path is guaranteed inside originals_dir.  Resolve as
        # a final defence if storage_dir is a symlink or has unusual casing.
        if self.originals_dir not in source_path.resolve().parents:
            raise DocumentServiceError("STORAGE_BOUNDARY", "無法建立安全的文件儲存位置")
        source_path.write_bytes(content)
        metadata = {"policy_refs": list(policy_refs or [])}
        imported_at = _utc_now()
        try:
            with self._connect() as db:
                db.execute(
                    """INSERT INTO documents
                    (doc_id, document_version, title, filename, source_type,
                     is_synthetic, content_hash, imported_at, processing_status,
                     processing_warnings, source_path, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, version, title.strip(), filename, suffix.lstrip("."),
                     int(is_synthetic), digest, imported_at, parse_status,
                     _json(warnings), str(source_path), _json(metadata)),
                )
                for number, (text, location, chunk_warnings) in enumerate(chunks, 1):
                    chunk_id = f"{doc_id}_chunk_{number:04d}"
                    db.execute(
                        "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                        (chunk_id, doc_id, version, text, _json(location), _json(chunk_warnings)),
                    )
                    db.execute("INSERT INTO chunks_fts(chunk_id, doc_id, text) VALUES (?, ?, ?)", (chunk_id, doc_id, text))
        except Exception:
            # The original is not useful without its index.  Remove only this
            # generated file; pre-existing documents are never touched.
            source_path.unlink(missing_ok=True)
            raise
        return self.detail(doc_id)

    def _parse(self, filename: str, content: bytes, version: str) -> tuple[list[tuple[str, dict[str, Any], list[str]]], list[str], str]:
        suffix = Path(filename).suffix.lower()
        if suffix in {".txt", ".md", ".markdown"}:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise DocumentServiceError("DECODE_FAILED", "文字文件必須使用 UTF-8 編碼") from exc
            chunks = self._text_chunks(text, suffix == ".md" or suffix == ".markdown")
            if not chunks:
                return [], ["empty_text"], "empty"
            return chunks, [], "indexed"

        warnings: list[str] = []
        try:
            from pypdf import PdfReader  # type: ignore

            import io
            reader = PdfReader(io.BytesIO(content))
            chunks: list[tuple[str, dict[str, Any], list[str]]] = []
            for page_no, page in enumerate(reader.pages, 1):
                page_text = (page.extract_text() or "").strip()
                if not page_text:
                    warnings.append(f"page_{page_no}_requires_ocr")
                    continue
                if self._looks_like_table(page_text):
                    warnings.append(f"page_{page_no}_table_needs_review")
                    continue
                chunks.extend(self._text_chunks(page_text, False, page_no=page_no))
            if not chunks:
                if any("table_needs_review" in warning for warning in warnings):
                    return [], warnings, "needs_review"
                warnings.append("scanned_pdf_requires_ocr")
                return [], warnings, "needs_ocr"
            if warnings:
                return chunks, warnings, "indexed_with_warnings"
            return chunks, warnings, "indexed"
        except DocumentServiceError:
            raise
        except Exception as exc:
            # Do not expose parser internals, paths or PDF metadata in API
            # errors.  Keep a diagnostic category in the document record.
            return [], ["pdf_parse_failed", type(exc).__name__], "parse_failed"

    @staticmethod
    def _looks_like_table(text: str) -> bool:
        lines = [line for line in text.splitlines() if line.strip()]
        if any(line.lstrip().startswith("|") and line.rstrip().endswith("|") for line in lines):
            return True
        # Extractors commonly turn table columns into tab characters or long
        # runs of spaces.  Keep such pages out of usable evidence until a
        # human checks the original layout.
        tabbed = sum("\t" in line for line in lines)
        spaced = sum(bool(re.search(r"\S\s{3,}\S", line)) for line in lines)
        return tabbed >= 2 or spaced >= 3

    def _text_chunks(self, text: str, markdown: bool, *, page_no: int | None = None) -> list[tuple[str, dict[str, Any], list[str]]]:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if not lines or not "".join(lines).strip():
            return []
        heading_path: list[str] = []
        units: list[tuple[str, dict[str, Any]]] = []
        current: list[str] = []
        start_line = 1

        def flush(end_line: int) -> None:
            nonlocal current, start_line
            value = "\n".join(current).strip()
            if value:
                loc: dict[str, Any] = {"start_line": start_line, "end_line": end_line}
                if page_no is not None:
                    loc = {"page": page_no, **loc}
                if heading_path:
                    loc["heading_path"] = list(heading_path)
                units.append((value, loc))
            current = []

        for line_no, line in enumerate(lines, 1):
            if markdown and re.match(r"^#{1,6}\s+", line):
                flush(line_no - 1)
                level = len(line) - len(line.lstrip("#"))
                heading = line[level:].strip()
                heading_path[:] = heading_path[: level - 1] + [heading]
            if not current:
                start_line = line_no
            current.append(line)
        flush(len(lines))

        result: list[tuple[str, dict[str, Any], list[str]]] = []
        for value, loc in units:
            if len(value) <= _MAX_CHUNK_CHARS:
                result.append((value, loc, []))
                continue
            start = 0
            part = 0
            while start < len(value):
                end = min(start + _MAX_CHUNK_CHARS, len(value))
                piece = value[start:end].strip()
                if piece:
                    piece_loc = dict(loc)
                    piece_loc["part"] = part
                    result.append((piece, piece_loc, ["long_text_split"] if part else []))
                if end >= len(value):
                    break
                start = max(end - _OVERLAP_CHARS, start + 1)
                part += 1
        return result

    def _document_row(self, row: sqlite3.Row, *, deduplicated: bool = False) -> dict[str, Any]:
        warnings = json.loads(row["processing_warnings"] or "[]")
        result = {
            "doc_id": row["doc_id"],
            "document_version": row["document_version"],
            "title": row["title"],
            "filename": row["filename"],
            "source_type": row["source_type"],
            "is_synthetic": bool(row["is_synthetic"]),
            "hash": row["content_hash"],
            "content_hash": row["content_hash"],
            "imported_at": row["imported_at"],
            "processing_status": row["processing_status"],
            "processing_warnings": warnings,
            "chunk_count": self._chunk_count(row["doc_id"]),
            "metadata": json.loads(row["metadata"] or "{}"),
        }
        if deduplicated:
            result["deduplicated"] = True
        return result

    def _chunk_count(self, doc_id: str) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT count(*) FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()[0])

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM documents ORDER BY imported_at, doc_id").fetchall()
        return [self._document_row(row) for row in rows]

    def detail(self, doc_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
            if row is None:
                raise DocumentServiceError("DOCUMENT_NOT_FOUND", "找不到文件")
            chunks = db.execute(
                "SELECT chunk_id, document_version, text, location, parse_warnings FROM chunks WHERE doc_id = ? ORDER BY chunk_id",
                (doc_id,),
            ).fetchall()
        result = self._document_row(row)
        result["chunks"] = [
            {"chunk_id": c["chunk_id"], "document_version": c["document_version"],
             "text": c["text"], "location": json.loads(c["location"]),
             "parse_warnings": json.loads(c["parse_warnings"] or "[]")}
            for c in chunks
        ]
        return result

    def source(self, doc_id: str) -> tuple[Path, str]:
        with self._connect() as db:
            row = db.execute("SELECT source_path, source_type FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        if row is None:
            raise DocumentServiceError("DOCUMENT_NOT_FOUND", "找不到文件")
        path = Path(row["source_path"]).resolve()
        if self.originals_dir not in path.parents or not path.is_file():
            raise DocumentServiceError("SOURCE_UNAVAILABLE", "原始文件不可用")
        mime = {"pdf": "application/pdf", "md": "text/markdown", "markdown": "text/markdown", "txt": "text/plain"}.get(row["source_type"], "application/octet-stream")
        return path, mime

    def _embedding_identity(self) -> dict[str, str]:
        provider = self.embedding_provider
        name = str(getattr(provider, "provider", getattr(provider, "provider_name", type(provider).__name__)))
        model = str(getattr(provider, "model", "custom"))
        base_url = str(getattr(provider, "base_url", "custom"))
        prompt_version = str(getattr(provider, "prompt_version", _EMBEDDING_PROMPT_VERSION))
        identity = {"provider": name, "model": model, "base_url": base_url, "prompt_version": prompt_version}
        identity["fingerprint"] = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
        return identity

    @staticmethod
    def _validate_vectors(vectors: Any, expected_count: int | None = None) -> tuple[list[list[float]], int]:
        if not isinstance(vectors, (list, tuple)):
            raise EmbeddingError("embedding provider returned a non-list")
        if expected_count is not None and len(vectors) != expected_count:
            raise EmbeddingError("embedding provider returned the wrong number of vectors")
        result: list[list[float]] = []
        dimensions: int | None = None
        for vector in vectors:
            if not isinstance(vector, (list, tuple)) or not vector:
                raise EmbeddingError("embedding provider returned an empty vector")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in vector):
                raise EmbeddingError("embedding provider returned a non-finite vector")
            values = [float(value) for value in vector]
            norm = math.sqrt(sum(value * value for value in values))
            if not math.isfinite(norm) or norm == 0:
                raise EmbeddingError("embedding provider returned a zero vector")
            if dimensions is None:
                dimensions = len(values)
            elif len(values) != dimensions:
                raise EmbeddingError("embedding provider returned inconsistent dimensions")
            result.append([value / norm for value in values])
        if not result:
            raise EmbeddingError("embedding provider returned no vectors")
        return result, int(dimensions or 0)

    @staticmethod
    def _embedding_warning(error: Exception) -> str:
        message = str(error).casefold()
        if "unavailable" in message:
            return "embedding_unavailable"
        if any(term in message for term in ("non-finite", "zero vector", "empty vector", "invalid response", "non-list")):
            return "embedding_invalid_vector"
        if any(term in message for term in ("dimension", "number of vectors")):
            return "embedding_dimension_mismatch"
        return "embedding_failed"

    @staticmethod
    def _validate_scope(scope: str) -> str:
        value = str(scope or "synthetic").strip().lower()
        if value not in _DOCUMENT_SCOPES:
            raise DocumentServiceError("INVALID_SCOPE", "scope 必須是 synthetic 或 reference")
        return value

    @staticmethod
    def _scope_is_synthetic(scope: str) -> bool:
        return scope == "synthetic"

    @staticmethod
    def _no_documents_warning(scope: str) -> str:
        return "no_synthetic_documents" if scope == "synthetic" else "no_reference_documents"

    def status(self, *, scope: str = "synthetic") -> dict[str, Any]:
        """Return retrieval configuration and local index counts.

        ``configured`` describes configuration presence, not whether an
        Ollama server is reachable; health is tested only during retrieval.
        """
        scope = self._validate_scope(scope)
        identity = self._embedding_identity()
        with self._connect() as db:
            scope_value = int(self._scope_is_synthetic(scope))
            total = int(db.execute("SELECT count(*) FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.is_synthetic=?", (scope_value,)).fetchone()[0])
            indexed = int(db.execute("SELECT count(*) FROM chunk_embeddings e JOIN chunks c ON c.chunk_id=e.chunk_id JOIN documents d ON d.doc_id=c.doc_id WHERE d.is_synthetic=? AND e.fingerprint=?", (scope_value, identity["fingerprint"])).fetchone()[0])
        return {
            "retrieval_method": "lexical" if self.retrieval_mode == "lexical" else "ollama_embeddings",
            "retrieval_mode": self.retrieval_mode,
            "provider": identity["provider"], "model": identity["model"],
            "embedding_provider": identity["provider"], "embedding_model": identity["model"],
            "base_url_configured": bool(identity["base_url"]), "prompt_version": identity["prompt_version"],
            "configured": self.retrieval_mode == "lexical" or bool(identity["model"] and identity["base_url"]),
            "scope": scope,
            "index": {"chunks": total, "embedded_chunks": indexed, "missing_chunks": max(0, total - indexed)},
            "warnings": list(self._configuration_warnings),
        }

    def _permitted_doc_ids(self, db: sqlite3.Connection, policy_refs: list[str] | None, scope: str = "synthetic") -> tuple[list[sqlite3.Row], set[str]]:
        scope = self._validate_scope(scope)
        docs = db.execute("SELECT * FROM documents WHERE is_synthetic = ?", (int(self._scope_is_synthetic(scope)),)).fetchall()
        requested_refs = {str(ref) for ref in (policy_refs or [])}
        permitted = {
            row["doc_id"] for row in docs
            if not requested_refs
            or requested_refs.intersection(json.loads(row["metadata"] or "{}").get("policy_refs", []))
            or row["doc_id"] in requested_refs
            or row["document_version"] in requested_refs
            or row["title"] in requested_refs
        }
        return docs, permitted

    def _store_embeddings(self, db: sqlite3.Connection, rows: Sequence[sqlite3.Row], vectors: Any, *, expected_dimensions: int | None = None) -> int:
        checked, dimensions = self._validate_vectors(vectors, len(rows))
        if expected_dimensions is not None and dimensions != expected_dimensions:
            raise EmbeddingError("embedding dimensions do not match")
        identity = self._embedding_identity()
        existing_dimensions = db.execute(
            "SELECT DISTINCT dimensions FROM chunk_embeddings WHERE fingerprint=?",
            (identity["fingerprint"],),
        ).fetchall()
        if any(int(item[0]) != dimensions for item in existing_dimensions):
            raise EmbeddingError("embedding dimensions do not match")
        for row, vector in zip(rows, checked):
            db.execute(
                """INSERT INTO chunk_embeddings
                (chunk_id, fingerprint, provider, model, base_url, prompt_version,
                 dimensions, vector_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, fingerprint) DO UPDATE SET
                  provider=excluded.provider, model=excluded.model,
                  base_url=excluded.base_url, prompt_version=excluded.prompt_version,
                  dimensions=excluded.dimensions, vector_json=excluded.vector_json,
                  created_at=excluded.created_at""",
                (row["chunk_id"], identity["fingerprint"], identity["provider"], identity["model"], identity["base_url"], identity["prompt_version"], dimensions, _json(vector), _utc_now()),
            )
        return len(checked)

    def _embed_query(self, query: str) -> Any:
        method = getattr(self.embedding_provider, "embed_query", None)
        if callable(method):
            vectors = method(query)
        else:
            embed = getattr(self.embedding_provider, "embed", self.embedding_provider if callable(self.embedding_provider) else None)
            if not callable(embed):
                raise EmbeddingError("embedding provider unavailable")
            vectors = embed([query])
        if isinstance(vectors, (list, tuple)) and vectors and isinstance(vectors[0], (int, float)):
            return [vectors]
        return vectors

    def _embed_documents(self, documents: Sequence[str]) -> Any:
        method = getattr(self.embedding_provider, "embed_documents", None)
        if callable(method):
            return method(documents)
        embed = getattr(self.embedding_provider, "embed", self.embedding_provider if callable(self.embedding_provider) else None)
        if not callable(embed):
            raise EmbeddingError("embedding provider unavailable")
        return embed(list(documents))

    def reindex(self, *, policy_refs: list[str] | None = None, scope: str = "synthetic") -> dict[str, Any]:
        """Embed all eligible chunks for the current provider identity."""
        scope = self._validate_scope(scope)
        if self.retrieval_mode == "lexical":
            info = self.status(scope=scope)
            info.update({"status": "skipped", "count": 0, "warnings": sorted(set(info.get("warnings", []) + ["lexical_mode_enabled"]))})
            return info
        outcome = "no_documents"
        outcome_warnings: list[str] = []
        count = 0
        with self._connect() as db:
            docs, permitted = self._permitted_doc_ids(db, policy_refs, scope)
            if not docs:
                outcome_warnings = [self._no_documents_warning(scope)]
            else:
                rows = db.execute(
                    f"SELECT c.* FROM chunks c WHERE c.doc_id IN ({','.join('?' for _ in permitted)}) ORDER BY c.chunk_id",
                    tuple(permitted),
                ).fetchall() if permitted else []
                if not rows:
                    outcome = "no_results"
                    outcome_warnings = ["no_eligible_chunks"]
                else:
                    try:
                        # Ollama may take minutes for a book. Compute every
                        # batch before opening a write transaction: SQLite
                        # cache spills otherwise block concurrent readers.
                        prepared = []
                        for start in range(0, len(rows), _EMBEDDING_BATCH_SIZE):
                            batch = rows[start:start + _EMBEDDING_BATCH_SIZE]
                            vectors = self._embed_documents([row["text"] for row in batch])
                            self._validate_vectors(vectors, len(batch))
                            prepared.append((batch, vectors))
                        # Replace only this identity's selected vectors in the
                        # same transaction so a failed rebuild restores them.
                        db.execute(
                            f"DELETE FROM chunk_embeddings WHERE fingerprint=? AND chunk_id IN (SELECT chunk_id FROM chunks WHERE doc_id IN ({','.join('?' for _ in permitted)}))",
                            (self._embedding_identity()["fingerprint"], *permitted),
                        )
                        for batch, vectors in prepared:
                            count += self._store_embeddings(db, batch, vectors)
                        outcome = "ok"
                    except EmbeddingError as exc:
                        db.rollback()
                        outcome = "failed"
                        count = 0
                        outcome_warnings = [self._embedding_warning(exc)]
                    except Exception:
                        db.rollback()
                        outcome = "failed"
                        count = 0
                        outcome_warnings = ["embedding_failed"]
        info = self.status(scope=scope)
        info["scope"] = scope
        info.update({"status": outcome, "count": count, "warnings": sorted(set(info.get("warnings", []) + outcome_warnings))})
        return info

    def _embedding_search(self, query: str, limit: int, policy_refs: list[str] | None, scope: str = "synthetic") -> dict[str, Any]:
        warnings: list[str] = []
        scope = self._validate_scope(scope)
        identity = self._embedding_identity()
        with self._connect() as db:
            docs, permitted = self._permitted_doc_ids(db, policy_refs, scope)
            if not docs:
                return {"status": "no_documents", "evidence": [], "warnings": [self._no_documents_warning(scope)], "retrieval_method": "ollama_embeddings", "scope": scope}
            if not permitted:
                return {"status": "no_results", "evidence": [], "warnings": ["policy_filter_no_match"], "retrieval_method": "ollama_embeddings", "scope": scope}
            rows = db.execute(
                f"SELECT c.*, d.title, d.is_synthetic, d.content_hash, d.source_type FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE c.doc_id IN ({','.join('?' for _ in permitted)}) ORDER BY c.chunk_id",
                tuple(permitted),
            ).fetchall()
            if not rows:
                return {"status": "no_results", "evidence": [], "warnings": ["no_eligible_chunks"], "retrieval_method": "ollama_embeddings", "scope": scope}
            try:
                query_vectors = self._embed_query(query)
                checked_query, query_dimensions = self._validate_vectors(query_vectors, 1)
                query_vector = checked_query[0]
                indexed = db.execute(
                    f"SELECT e.*, c.*, d.title, d.is_synthetic, d.content_hash, d.source_type FROM chunk_embeddings e JOIN chunks c ON c.chunk_id=e.chunk_id JOIN documents d ON d.doc_id=c.doc_id WHERE e.fingerprint=? AND c.doc_id IN ({','.join('?' for _ in permitted)})",
                    (identity["fingerprint"], *permitted),
                ).fetchall()
                indexed_ids = {row["chunk_id"] for row in indexed}
                missing_rows = [row for row in rows if row["chunk_id"] not in indexed_ids]
                if missing_rows:
                    prepared = []
                    for start in range(0, len(missing_rows), _EMBEDDING_BATCH_SIZE):
                        batch = missing_rows[start:start + _EMBEDDING_BATCH_SIZE]
                        vectors = self._embed_documents([row["text"] for row in batch])
                        _, dimensions = self._validate_vectors(vectors, len(batch))
                        if dimensions != query_dimensions:
                            raise EmbeddingError("embedding dimensions do not match")
                        prepared.append((batch, vectors))
                    for batch, vectors in prepared:
                        self._store_embeddings(db, batch, vectors, expected_dimensions=query_dimensions)
                    indexed = db.execute(
                        f"SELECT e.*, c.*, d.title, d.is_synthetic, d.content_hash, d.source_type FROM chunk_embeddings e JOIN chunks c ON c.chunk_id=e.chunk_id JOIN documents d ON d.doc_id=c.doc_id WHERE e.fingerprint=? AND c.doc_id IN ({','.join('?' for _ in permitted)})",
                        (identity["fingerprint"], *permitted),
                    ).fetchall()
                scored: list[tuple[float, sqlite3.Row]] = []
                for row in indexed:
                    vector, dimensions = self._validate_vectors([json.loads(row["vector_json"])], 1)
                    if dimensions != query_dimensions:
                        raise EmbeddingError("embedding dimensions do not match")
                    score = sum(a * b for a, b in zip(query_vector, vector[0]))
                    if math.isfinite(score) and score > 0:
                        scored.append((score, row))
                scored.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
                evidence = [self._evidence_row(row, score) for score, row in scored[:limit]]
            except EmbeddingError as exc:
                db.rollback()
                return {"status": "failed", "evidence": [], "warnings": [self._embedding_warning(exc)], "retrieval_method": "ollama_embeddings", "scope": scope}
            except Exception:
                db.rollback()
                return {"status": "failed", "evidence": [], "warnings": ["embedding_failed"], "retrieval_method": "ollama_embeddings", "scope": scope}
            warnings.extend(json.loads(doc["processing_warnings"] or "[]") for doc in docs)
            warnings = [warning for group in warnings for warning in (group if isinstance(group, list) else [group])]
            for row in indexed:
                warnings.extend(json.loads(row["parse_warnings"] or "[]"))
        version_groups: dict[str, set[str]] = {}
        returned_titles = {item["document_title"] for item in evidence}
        for row in docs:
            if row["doc_id"] in permitted and row["title"] in returned_titles:
                version_groups.setdefault(row["title"], set()).add(row["document_version"])
        conflict = any(len(versions) > 1 for versions in version_groups.values())
        if conflict:
            warnings.append("document_version_conflict")
            evidence = []
        return {"status": "conflict" if conflict else ("ok" if evidence else "no_results"), "evidence": evidence, "warnings": sorted(set(warnings)), "retrieval_method": "ollama_embeddings", "scope": scope}

    @staticmethod
    def _evidence_row(row: sqlite3.Row, score: float | None = None) -> dict[str, Any]:
        location = json.loads(row["location"])
        result = {
            "chunk_id": row["chunk_id"], "doc_id": row["doc_id"], "document_version": row["document_version"], "document_title": row["title"],
            "text": row["text"], "location": location, "parse_warnings": json.loads(row["parse_warnings"] or "[]"),
            "content_hash": row["content_hash"], "is_synthetic": bool(row["is_synthetic"]), "source_type": row["source_type"], "source_location": location,
        }
        if score is not None:
            result["score"] = round(float(score), 8)
        return result

    def search(self, query: str, limit: int = 8, policy_refs: list[str] | None = None, *, scope: str = "synthetic") -> dict[str, Any]:
        scope = self._validate_scope(scope)
        if self.retrieval_mode == "lexical":
            return self._lexical_search(query, limit, policy_refs, scope)
        warnings: list[str] = []
        identity = self._embedding_identity()
        if not isinstance(query, str) or not query.strip():
            return {"status": "empty_query", "evidence": [], "warnings": ["query_required"], "retrieval_method": "ollama_embeddings", "embedding_model": identity["model"], "embedding_provider": identity["provider"], "scope": scope}
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 8
            warnings.append("invalid_limit_defaulted")
        result = self._embedding_search(query, limit, policy_refs, scope)
        result["embedding_model"] = identity["model"]
        result["embedding_provider"] = identity["provider"]
        if warnings:
            result["warnings"] = sorted(set(result.get("warnings", []) + warnings))
        return result

    def _lexical_search(self, query: str, limit: int = 8, policy_refs: list[str] | None = None, scope: str = "synthetic") -> dict[str, Any]:
        warnings: list[str] = []
        scope = self._validate_scope(scope)
        if not isinstance(query, str) or not query.strip():
            return {"status": "empty_query", "evidence": [], "warnings": ["query_required"], "retrieval_method": "lexical", "scope": scope}
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 8
            warnings.append("invalid_limit_defaulted")
        with self._connect() as db:
            docs = db.execute("SELECT * FROM documents WHERE is_synthetic = ?", (int(self._scope_is_synthetic(scope)),)).fetchall()
            if not docs:
                return {"status": "no_documents", "evidence": [], "warnings": [self._no_documents_warning(scope)], "retrieval_method": "lexical", "scope": scope}
            for doc in docs:
                warnings.extend(json.loads(doc["processing_warnings"] or "[]"))
            requested_refs = {str(ref) for ref in (policy_refs or [])}
            permitted = {
                row["doc_id"] for row in docs
                if not requested_refs
                or requested_refs.intersection(json.loads(row["metadata"] or "{}").get("policy_refs", []))
                or row["doc_id"] in requested_refs
                or row["document_version"] in requested_refs
                or row["title"] in requested_refs
            }
            if not permitted:
                return {"status": "no_results", "evidence": [], "warnings": ["policy_filter_no_match"], "retrieval_method": "lexical", "scope": scope}
            # FTS query syntax is intentionally generated from tokens, so a
            # user cannot inject operators or arbitrary SQL.
            tokens = re.findall(r"[\w\u4e00-\u9fff]+", query.casefold())
            match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
            rows: list[sqlite3.Row] = []
            retrieval_method = "lexical"
            if match:
                placeholders = ",".join("?" for _ in permitted)
                try:
                    rows = db.execute(
                        f"""SELECT c.*, d.title, d.is_synthetic, d.content_hash, d.source_type
                        FROM chunks_fts f JOIN chunks c ON c.chunk_id=f.chunk_id
                        JOIN documents d ON d.doc_id=c.doc_id
                        WHERE chunks_fts MATCH ? AND c.doc_id IN ({placeholders})
                        LIMIT ?""",
                        (match, *permitted, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    warnings.append("fts_unavailable_keyword_fallback")
            if not rows:
                # Fallback also handles CJK tokenization and minimal SQLite
                # builds without FTS5.
                retrieval_method = "lexical"
                lowered = query.casefold()
                rows = db.execute(
                    f"""SELECT c.*, d.title, d.is_synthetic, d.content_hash, d.source_type
                    FROM chunks c JOIN documents d ON d.doc_id=c.doc_id
                    WHERE c.doc_id IN ({','.join('?' for _ in permitted)})
                    ORDER BY c.chunk_id""", tuple(permitted),
                ).fetchall()
                scored = [(sum(1 for token in tokens if token in c["text"].casefold()) or (1 if lowered in c["text"].casefold() else 0), c) for c in rows]
                rows = [c for score, c in sorted(scored, key=lambda x: (-x[0], x[1]["chunk_id"])) if score > 0][:limit]
            evidence = []
            for row in rows:
                evidence.append({
                    "chunk_id": row["chunk_id"], "doc_id": row["doc_id"],
                    "document_version": row["document_version"], "document_title": row["title"],
                    "text": row["text"], "location": json.loads(row["location"]),
                    "parse_warnings": json.loads(row["parse_warnings"] or "[]"),
                    "content_hash": row["content_hash"], "is_synthetic": bool(row["is_synthetic"]),
                    "source_type": row["source_type"],
                    "source_location": json.loads(row["location"]),
                })
                warnings.extend(json.loads(row["parse_warnings"] or "[]"))
        version_groups: dict[str, set[str]] = {}
        # Conflicts must not disappear when a small result limit happens to
        # return chunks from only one version of an otherwise ambiguous policy.
        returned_titles = {item['document_title'] for item in evidence}
        for row in docs:
            if row['doc_id'] in permitted and row['title'] in returned_titles:
                version_groups.setdefault(row['title'], set()).add(row['document_version'])
        conflict = any(len(versions) > 1 for versions in version_groups.values())
        if conflict:
            warnings.append("document_version_conflict")
            # Never silently blend two versions.  A caller can pin a version,
            # doc_id or policy reference to obtain one unambiguous snapshot.
            evidence = []
        status = "conflict" if conflict else ("ok" if evidence else "no_results")
        return {"status": status, "evidence": evidence, "warnings": sorted(set(warnings)), "retrieval_method": retrieval_method, "scope": scope}
