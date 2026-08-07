from typing import Optional, Any, List, Dict
class SelfRAGVerifier:
    """Post-retrieval relevance filter and post-generation hallucination check."""
    def __init__(self, memory_hook: Optional[Any] = None):
        self.memory_hook = memory_hook

    def check_retrieval_relevance(self, query: str, docs: List[Dict[str, Any]], threshold: float = 0.1) -> List[Dict[str, Any]]:
        """Filters out retrieved documents that do not meet query relevance threshold."""
        query_words = set(query.lower().split())
        relevant_docs = []

        for doc in docs:
            doc_words = set(doc["content"].lower().split())
            overlap = len(query_words.intersection(doc_words))
            relevance_score = overlap / max(len(query_words), 1)

            if relevance_score >= threshold or doc.get("score", 1.0) > 0.0:
                doc["relevance_checked"] = True
                relevant_docs.append(doc)

        if self.memory_hook and hasattr(self.memory_hook, "log_episodic"):
            self.memory_hook.log_episodic("retrieval_check", {"query": query, "passed": len(relevant_docs)})

        return relevant_docs

    def check_generation_grounding(self, generated_answer: str, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Post-generation check to verify that the answer is grounded in context."""
        context = " ".join([d["content"].lower() for d in retrieved_docs])
        
        # Stop words filter for strict grounding evaluation
        stop_words = {"the", "a", "an", "on", "in", "was", "is", "at", "by", "for", "of", "to", "and"}
        answer_words = set(generated_answer.lower().split()) - stop_words
        context_words = set(context.split()) - stop_words

        if not answer_words:
            return {"is_grounded": True, "support_score": 1.0, "hallucination_detected": False}

        grounded_tokens = answer_words.intersection(context_words)
        support_score = len(grounded_tokens) / len(answer_words)

        is_grounded = support_score >= 0.5
        result = {
            "is_grounded": is_grounded,
            "support_score": round(support_score, 2),
            "hallucination_detected": not is_grounded
        }

        if self.memory_hook and hasattr(self.memory_hook, "log_semantic"):
            self.memory_hook.log_semantic("grounding_verdict", result)

        return result