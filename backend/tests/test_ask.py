from tests.conftest import FakePipeline


def test_ask_happy_path(client):
    res = client.post("/ask", json={"question": "How do I merge two dictionaries?"})
    assert res.status_code == 200
    body = res.json()
    assert body["grounded"] is True
    assert "merge" in body["answer"].lower()
    assert len(body["sources"]) == 1
    src = body["sources"][0]
    assert src["link"].startswith("https://stackoverflow.com/")
    assert src["question_score"] > 0
    assert body["latency_ms"] >= 0
    assert body["model"] == "fake-model"


def test_ask_out_of_scope_question(app, client):
    app.state.pipeline = FakePipeline(grounded=False)
    res = client.post("/ask", json={"question": "What is the capital of France?"})
    assert res.status_code == 200
    body = res.json()
    assert body["grounded"] is False
    assert body["sources"] == []
    assert "knowledge base" in body["answer"]


def test_ask_missing_question_field(client):
    res = client.post("/ask", json={})
    assert res.status_code == 422


def test_ask_empty_question(client):
    res = client.post("/ask", json={"question": ""})
    assert res.status_code == 422


def test_ask_too_short_question(client):
    res = client.post("/ask", json={"question": "py"})
    assert res.status_code == 422


def test_ask_too_long_question(client):
    res = client.post("/ask", json={"question": "x" * 2001})
    assert res.status_code == 422


def test_ask_wrong_type(client):
    res = client.post("/ask", json={"question": 12345})
    assert res.status_code == 422


def test_ask_pipeline_not_initialised_returns_503(app, client):
    app.state.pipeline = None
    res = client.post("/ask", json={"question": "How do list comprehensions work?"})
    assert res.status_code == 503
    assert "not initialised" in res.json()["detail"]


def test_ask_pipeline_failure_returns_502(app, client):
    app.state.pipeline = FakePipeline(error=RuntimeError("LLM quota exceeded"))
    res = client.post("/ask", json={"question": "How do list comprehensions work?"})
    assert res.status_code == 502
    assert "RuntimeError" in res.json()["detail"]
