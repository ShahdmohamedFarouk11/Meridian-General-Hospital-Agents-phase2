import pytest
from rag.vector_store.store import VectorStore

@pytest.fixture
def store():
    store_inst = VectorStore(dim=384)
    docs = [
        {"content": "Civil case contract agreement signed in Cairo court.", "metadata": {"jurisdiction": "cairo", "type": "civil", "case_id": "C-101"}},
        {"content": "Medical malpractice claim involving Alexandria Hospital.", "metadata": {"jurisdiction": "alexandria", "type": "medical", "case_id": "M-202"}},
        {"content": "IP Patent dispute over artificial intelligence software.", "metadata": {"jurisdiction": "cairo", "type": "ip", "case_id": "IP-303"}}
    ]
    store_inst.add_documents(docs)
    return store_inst

def test_chunking_and_ingestion(store):
    chunks = store.chunk_text("Word " * 300, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert len(store.payload_store) == 3

def test_hnsw_ann_search(store):
    results = store.search("contract agreement Cairo", top_k=2)
    assert len(results) <= 2
    assert len(results) > 0
    assert "content" in results[0]
    assert "score" in results[0]

def test_metadata_filtering(store):
    # Filter for alexandria
    alex_results = store.search("claim", top_k=5, filters={"jurisdiction": "alexandria"})
    assert len(alex_results) == 1
    assert alex_results[0]["metadata"]["case_id"] == "M-202"

    # Filter with no matches
    no_results = store.search("claim", top_k=5, filters={"jurisdiction": "giza"})
    assert len(no_results) == 0