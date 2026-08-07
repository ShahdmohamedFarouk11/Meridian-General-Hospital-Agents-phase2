import math
from typing import List, Dict, Any, Optional
from collections import defaultdict
from .vector_store.store import VectorStore

class BM25Index:
    """Sparse keyword search implementation for Hybrid Search."""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_len = {}
        self.avg_doc_len = 0.0
        self.doc_freqs = defaultdict(int)
        self.idf = {}
        self.documents = []

    def fit(self, docs: List[Dict[str, Any]]):
        self.documents = docs
        total_len = 0
        for i, doc in enumerate(docs):
            tokens = doc["content"].lower().split()
            self.doc_len[i] = len(tokens)
            total_len += len(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        self.avg_doc_len = total_len / max(len(docs), 1)
        num_docs = len(docs)
        for token, freq in self.doc_freqs.items():
            self.idf[token] = math.log((num_docs - freq + 0.5) / (freq + 0.5) + 1)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        tokens = query.lower().split()
        scores = defaultdict(float)
        for i, doc in enumerate(self.documents):
            doc_tokens = doc["content"].lower().split()
            for token in tokens:
                if token not in doc_tokens:
                    continue
                tf = doc_tokens.count(token)
                idf_val = self.idf.get(token, 0.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[i] / max(self.avg_doc_len, 1e-5)))
                scores[i] += idf_val * (numerator / denominator)

        sorted_indices = sorted(scores.keys(), key=lambda idx: scores[idx], reverse=True)[:top_k]
        results = []
        for idx in sorted_indices:
            results.append({
                "id": self.documents[idx]["id"],
                "content": self.documents[idx]["content"],
                "metadata": self.documents[idx].get("metadata", {}),
                "score": scores[idx]
            })
        return results

class HybridRAG:
    """Combines Dense Vector (HNSW) and Sparse Keyword (BM25) search via RRF."""
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.bm25 = BM25Index()

    def sync_bm25(self):
        docs = [payload for payload in self.vector_store.payload_store.values()]
        self.bm25.fit(docs)

    def retrieve(self, query: str, top_k: int = 3, rrf_k: int = 60, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        dense_results = self.vector_store.search(query=query, top_k=top_k * 2, filters=filters)
        self.sync_bm25()
        sparse_results = self.bm25.search(query=query, top_k=top_k * 2)

        rrf_scores = defaultdict(float)
        doc_map = {}

        for rank, doc in enumerate(dense_results):
            doc_id = doc["content"]
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            doc_map[doc_id] = doc

        for rank, doc in enumerate(sparse_results):
            doc_id = doc["content"]
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            doc_map[doc_id] = doc

        sorted_docs = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)[:top_k]
        final_results = []
        for d_key in sorted_docs:
            item = doc_map[d_key]
            item["score"] = rrf_scores[d_key]
            final_results.append(item)
        return final_results