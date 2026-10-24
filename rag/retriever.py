"""Búsqueda en la knowledge base: retrieval (Chroma) -> re-ranking (CrossEncoder).

Son las dos primeras etapas del pipeline del Taller 2. La tercera etapa
(generación) ya no vive aquí: ahora el agente recibe los fragmentos como
resultado de una herramienta y redacta la respuesta él mismo.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentence_transformers import CrossEncoder

from rag.ingest import load_vectorstore

CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Mismo umbral calibrado en el Taller 2: por debajo de este score del
# cross-encoder se considera que ningún fragmento es relevante.
RERANK_SCORE_THRESHOLD = -3.0

_cross_encoder: CrossEncoder | None = None
_vectorstore = None


@dataclass
class Chunk:
    content: str
    source: str
    retrieval_score: float
    rerank_score: float | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL_NAME)
    return _cross_encoder


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = load_vectorstore()
    return _vectorstore


def retrieve(query: str, top_k: int = 10) -> list[Chunk]:
    results = _get_vectorstore().similarity_search_with_score(query, k=top_k)
    return [
        Chunk(
            content=doc.page_content,
            source=doc.metadata.get("source", "desconocido"),
            retrieval_score=float(score),
        )
        for doc, score in results
    ]


def rerank(query: str, chunks: list[Chunk], top_n: int = 3) -> list[Chunk]:
    if not chunks:
        return []
    scores = _get_cross_encoder().predict([[query, c.content] for c in chunks])
    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = float(score)
    return sorted(chunks, key=lambda c: c.rerank_score, reverse=True)[:top_n]


def search(query: str, top_k: int = 10, top_n: int = 3) -> tuple[list[Chunk], bool]:
    """Devuelve (fragmentos re-rankeados, hay_informacion_relevante)."""
    reranked = rerank(query, retrieve(query, top_k=top_k), top_n=top_n)
    relevant = bool(reranked) and reranked[0].rerank_score >= RERANK_SCORE_THRESHOLD
    return reranked, relevant


def warmup() -> None:
    _get_vectorstore()
    _get_cross_encoder()
