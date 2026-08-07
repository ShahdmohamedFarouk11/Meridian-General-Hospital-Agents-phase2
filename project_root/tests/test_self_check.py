import pytest
from rag.self_check import SelfRAGVerifier

class MockDevAMemory:
    def __init__(self):
        self.episodic_logs = []
        self.semantic_logs = []

    def log_episodic(self, event, data):
        self.episodic_logs.append((event, data))

    def log_semantic(self, event, data):
        self.semantic_logs.append((event, data))

def test_post_retrieval_relevance_check():
    verifier = SelfRAGVerifier()
    retrieved_docs = [
        {"content": "Cairo court hearing scheduled for dispute.", "score": 0.8},
        {"content": "Unrelated topic recipe for baking bread.", "score": -0.5}
    ]
    
    # Query relevant check
    filtered = verifier.check_retrieval_relevance("Cairo court dispute", retrieved_docs)
    assert len(filtered) > 0

def test_post_generation_grounding_and_hallucination():
    memory = MockDevAMemory()
    verifier = SelfRAGVerifier(memory_hook=memory)
    
    context_docs = [{"content": "The defendant John Doe was present in court on Monday."}]
    
    # Valid grounded response
    grounded_eval = verifier.check_grounding_or_support if hasattr(verifier, 'check_grounding_or_support') else verifier.check_generation_grounding
    res_valid = grounded_eval("John Doe was present in court on Monday", context_docs)
    assert res_valid["is_grounded"] is True
    assert res_valid["hallucination_detected"] is False

    # Hallucinated response
    res_hallucinated = grounded_eval("The spacecraft landed on Mars in 2099", context_docs)
    assert res_hallucinated["is_grounded"] is False
    assert res_hallucinated["hallucination_detected"] is True
    
    # Check if memory hooks were triggered
    assert len(memory.semantic_logs) > 0