def test_health_returns_200(client):
    res = client.get("/health")
    assert res.status_code == 200


def test_health_shape(client):
    body = client.get("/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert "vector_db" in body
    assert isinstance(body["vector_db"]["connected"], bool)
    assert isinstance(body["vector_db"]["document_count"], int)
    assert body["model"]
    assert body["timestamp"]


def test_health_reports_empty_collection(client):
    body = client.get("/health").json()
    # Test Chroma dir is a fresh temp directory — collection exists but is empty.
    assert body["vector_db"]["connected"] is True
    assert body["vector_db"]["document_count"] == 0
    assert body["status"] == "ok"
