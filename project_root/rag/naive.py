from typing import List, Dict, Any, Optional
from .vector_store.store import VectorStore

class NaiveRAG:
    """Standard dense similarity search retrieval architecture."""
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.vector_store.search(query=query, top_k=top_k, filters=filters)