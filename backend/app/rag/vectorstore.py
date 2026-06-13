import chromadb
from langchain_chroma import Chroma

from app.core.config import get_settings
from app.rag.embeddings import get_embeddings


def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_dir)


def get_vectorstore() -> Chroma:
    settings = get_settings()
    return Chroma(
        client=get_chroma_client(),
        collection_name=settings.chroma_collection,
        embedding_function=get_embeddings(),
        collection_metadata={"hnsw:space": "cosine"},
    )


def get_document_count() -> int:
    settings = get_settings()
    client = get_chroma_client()
    collection = client.get_or_create_collection(settings.chroma_collection)
    return collection.count()
