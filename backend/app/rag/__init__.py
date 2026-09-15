"""Local document ingestion and retrieval for the prototype."""

from .service import (
    DocumentService,
    DocumentServiceError,
    EmbeddingError,
    OllamaEmbeddingAdapter,
    OllamaEmbeddingProvider,
)

__all__ = [
    "DocumentService", "DocumentServiceError", "EmbeddingError",
    "OllamaEmbeddingAdapter", "OllamaEmbeddingProvider",
]

from .service import DocumentService, DocumentServiceError, Retriever

__all__ = ["DocumentService", "DocumentServiceError", "Retriever"]
