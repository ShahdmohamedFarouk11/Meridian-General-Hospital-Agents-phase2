from typing import List, Dict, Any, Optional
from .vector_store.store import VectorStore

class AgenticRAG:
    """Multi-hop reasoning loop retrieval architecture."""
    def __init__(self, vector_store: VectorStore, max_hops: int = 3):
        self.vector_store = vector_store
        self.max_hops = max_hops

    def retrieve(self, initial_query: str, top_k: int = 3) -> Dict[str, Any]:
        retrieved_history = []
        seen_contents = set()
        current_query = initial_query

        for hop in range(self.max_hops):
            results = self.vector_store.search(query=current_query, top_k=top_k)
            new_info = False

            for res in results:
                if res["content"] not in seen_contents:
                    seen_contents.add(res["content"])
                    retrieved_history.append(res)
                    new_info = True

            if not new_info:
                break

            # Construct next multi-hop sub-query from gathered insights
            terms = current_query.split()
            current_query = f"{initial_query} context_hop_{hop+1} " + " ".join(terms[:2])

        return {
            "initial_query": initial_query,
            "total_hops": len(retrieved_history) // top_k + 1,
            "documents": retrieved_history[:top_k * 2]
        }