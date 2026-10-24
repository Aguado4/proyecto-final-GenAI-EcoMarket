"""Construye el índice vectorial (Chroma) a partir de la knowledge base de EcoMarket.

Uso:
    python -m rag.ingest

Mismo proceso del Taller 2 (justificación de embeddings, chunking y
base vectorial en el repo taller2-GenAI-EcoMarket):
  1. Carga los documentos de knowledge_base/*.md.
  2. Los segmenta en chunks con RecursiveCharacterTextSplitter.
  3. Los convierte en vectores con un modelo de embeddings open-source
     multilingüe.
  4. Los indexa en ChromaDB, persistido en disco (./chroma_db).
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
PERSIST_DIR = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "ecomarket_kb"

# Modelo de embeddings open-source, multilingüe (soporta español) y liviano
# para correr en CPU sin costo. Ver respuestas/fase1_seleccion_componentes.md
# para la justificación completa frente a alternativas propietarias.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Chunking recursivo: intenta cortar primero por párrafos, luego por
# oraciones, luego por palabras, solo si el fragmento sigue siendo
# demasiado grande. chunk_overlap conserva contexto entre fragmentos
# consecutivos para no cortar una idea a la mitad.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)


def load_knowledge_base_documents():
    """Carga cada archivo .md de knowledge_base/ como un Document de LangChain."""
    documents = []
    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        loader = TextLoader(str(md_file), encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = md_file.name
        documents.extend(docs)
    return documents


def build_vectorstore(reset: bool = True) -> Chroma:
    """Construye (o reconstruye) el índice de Chroma desde cero."""
    documents = load_knowledge_base_documents()
    if not documents:
        raise FileNotFoundError(f"No se encontraron documentos .md en {KNOWLEDGE_BASE_DIR}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    embeddings = get_embeddings()

    if reset:
        import shutil

        shutil.rmtree(PERSIST_DIR, ignore_errors=True)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
        collection_name=COLLECTION_NAME,
    )
    return vectorstore, chunks


def load_vectorstore() -> Chroma:
    """Carga el índice de Chroma ya existente en disco (sin reconstruirlo)."""
    embeddings = get_embeddings()
    return Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


def main() -> None:
    print(f"Cargando documentos desde {KNOWLEDGE_BASE_DIR}...")
    vectorstore, chunks = build_vectorstore(reset=True)
    print(f"Se crearon {len(chunks)} chunks a partir de los documentos de la knowledge base.")

    by_source: dict[str, int] = {}
    for chunk in chunks:
        source = chunk.metadata.get("source", "desconocido")
        by_source[source] = by_source.get(source, 0) + 1
    for source, count in sorted(by_source.items()):
        print(f"  - {source}: {count} chunks")

    print(f"\nÍndice de Chroma creado en {PERSIST_DIR} (colección '{COLLECTION_NAME}').")


if __name__ == "__main__":
    main()
