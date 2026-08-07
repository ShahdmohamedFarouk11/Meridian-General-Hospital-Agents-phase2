import pytest
from rag.vector_store.store import VectorStore
from rag.naive import NaiveRAG
from rag.hybrid import HybridRAG
from rag.agentic import AgenticRAG

@pytest.fixture
def rag_suite():
    store = VectorStore(dim=384)
    docs = [
        {"content": "Lawyer Smith filed a motion for summary judgment in civil court.", "metadata": {"type": "civil"}},
        {"content": "The contract clause 4 states terms of non-disclosure and NDA.", "metadata": {"type": "corporate"}},
        {"content": "Medical malpractice liability and doctor responsibility guidelines.", "metadata": {"type": "medical"}}
    ]
    store.add_documents(docs)
    return {
        "naive": NaiveRAG(store),
        "hybrid": HybridRAG(store),
        "agentic": AgenticRAG(store)
    }

def test_naive_rag_retrieval(rag_suite):
    results = rag_suite["naive"].retrieve("NDA contract clause", top_k=3)
    assert len(results) > 0
    all_content = " ".join([r["content"].lower() for r in results])
    assert "contract" in all_content or "motion" in all_content
def test_hybrid_bm25_dense_rrf(rag_suite):
    results = rag_suite["hybrid"].retrieve("summary judgment motion", top_k=2)
    assert len(results) > 0
    assert "score" in results[0]

def test_agentic_multihop_reasoning(rag_suite):
    response = rag_suite["agentic"].retrieve("medical malpractice doctor guidelines", top_k=1)
    assert "initial_query" in response
    assert "documents" in response
    assert response["total_hops"] >= 1
    assert len(response["documents"]) > 0