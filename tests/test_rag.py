"""RAG app checks with small fakes: no network, model download or API key.

The fakes stand in for fastembed and Groq so these tests check *our* code:
parsing, chunking, repeat import, the graph source check, retrieval, the
emergency and missing-evidence guards, citations, traces and permissions.
The real providers are checked separately on the server (see the record).
"""

import hashlib
import re

import pytest

from app import database
from app.rag import graph, importer, pipeline, store
from app.rag.providers import normalize

PASSWORD = "a disposable test password"

SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<nlmSearchResult><list num="2" start="0" per="20">
<document rank="0" url="https://medlineplus.gov/diabetestype2.html">
<content name="title">&lt;span class="qt0"&gt;Diabetes&lt;/span&gt; Type 2</content>
<content name="FullSummary">&lt;p&gt;Wrong page.&lt;/p&gt;</content>
</document>
<document rank="1" url="https://medlineplus.gov/diabetes.html">
<content name="title">&lt;span class="qt0"&gt;Diabetes&lt;/span&gt;</content>
<content name="FullSummary">&lt;h3&gt;What is diabetes?&lt;/h3&gt;&lt;p&gt;Diabetes is a disease in which your blood glucose, or blood sugar, levels are too high.&lt;/p&gt;&lt;p&gt;Symptoms of diabetes may include:&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Increased thirst and urination&lt;/li&gt;&lt;li&gt;Feeling tired&lt;/li&gt;&lt;/ul&gt;</content>
</document>
</list></nlmSearchResult>"""

PAGES = {
    "mlp-a": (
        "<p>Diabetes is a disease in which your blood sugar levels are too high.</p>"
        "<p>Symptoms of diabetes include increased thirst, frequent urination and "
        "feeling tired.</p>"
    ),
    "mlp-b": (
        "<p>Over time, high blood sugar can cause nerve damage and kidney disease.</p>"
    ),
}
MANIFEST = {
    "permission": "Public domain test text.",
    "sources": [
        {"id": "mlp-a", "title": "Diabetes", "url": "https://medlineplus.gov/a.html"},
        {
            "id": "mlp-b",
            "title": "Complications",
            "url": "https://medlineplus.gov/b.html",
        },
    ],
}


class FakeEmbedder:
    """Word-hashing vectors: similar wording gives similar vectors."""

    model = "fake-hash-64"

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            for word in re.findall(r"[a-z]+", text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1
            vectors.append(normalize(vector))
        return vectors


class FakeModel:
    """Records what it was sent and returns a scripted reply."""

    model = "fake-chat"

    def __init__(self, reply="Thirst is a common symptom. [S1]"):
        self.reply = reply
        self.calls = []

    def complete(self, messages, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        return self.reply


def run_import(settings, pages=None):
    pages = pages or PAGES
    embedder = FakeEmbedder()
    return importer.import_sources(
        settings,
        embedder.embed,
        embedder.model,
        lambda source: pages[source["id"]],
        MANIFEST,
    )


@pytest.fixture(autouse=True)
def fake_score_threshold(monkeypatch):
    """Word-hash vectors score lower than real embeddings; scale the cut-off."""
    monkeypatch.setattr(pipeline, "MIN_SCORE", 0.2)


# ------------------------------------------------------------------ import


def test_web_service_reply_is_matched_by_url_and_cleaned():
    """Only the requested page's summary is used, and its HTML becomes text."""
    title, summary = importer.parse_search(
        SEARCH_XML, "https://medlineplus.gov/diabetes.html"
    )
    assert title == "Diabetes"
    blocks = importer.paragraphs(summary)
    assert blocks[0] == "What is diabetes?"
    assert "• Increased thirst and urination" in blocks
    assert "Wrong page." not in " ".join(blocks)


def test_list_intro_stays_with_its_list_and_chunks_respect_the_limit():
    blocks = [
        "A" * 300 + ".",
        "Symptoms include:",
        "• thirst",
        "• tiredness",
        "B" * 600 + ".",
    ]
    pieces = importer.chunk(blocks, limit=700)
    assert any("Symptoms include:\n• thirst\n• tiredness" in piece for piece in pieces)
    assert all(len(piece) <= 700 for piece in pieces)


def test_repeat_import_does_not_duplicate_and_a_change_replaces_old_chunks(settings):
    database.initialize(settings)
    store.initialize(settings)
    first = run_import(settings)
    assert [row["status"] for row in first] == ["imported", "imported"]
    count = len(store.chunks(settings))
    assert [row["status"] for row in run_import(settings)] == ["unchanged", "unchanged"]
    assert len(store.chunks(settings)) == count
    changed = {**PAGES, "mlp-b": "<p>High blood sugar can damage your eyes.</p>"}
    run_import(settings, changed)
    texts = [
        row["text"] for row in store.chunks(settings) if row["source_id"] == "mlp-b"
    ]
    assert texts == ["High blood sugar can damage your eyes."]


# ------------------------------------------------------------------- graph


PASSAGE = "Over time, high blood sugar can cause nerve damage and kidney disease."


def test_graph_keeps_only_relationships_quoted_from_the_passage():
    good = {
        "subject": "High blood sugar",
        "relation": "causes",
        "object": "nerve damage",
        "evidence": "high blood sugar can cause nerve damage",
    }
    assert graph.check(good, PASSAGE)["subject"] == "high blood sugar"
    invented = {
        **good,
        "object": "hair loss",
        "evidence": "high blood sugar can cause hair loss",
    }
    wrong_relation = {**good, "relation": "cures"}
    missing_entity = {**good, "object": "eye damage"}
    assert graph.check(invented, PASSAGE) is None
    assert graph.check(wrong_relation, PASSAGE) is None
    assert graph.check(missing_entity, PASSAGE) is None


def test_graph_extraction_saves_kept_edges_and_counts_rejections(settings):
    database.initialize(settings)
    store.initialize(settings)
    run_import(settings)
    reply = (
        '{"relationships": [{"subject": "high blood sugar", "relation": "causes",'
        ' "object": "nerve damage", "evidence": "high blood sugar can cause nerve'
        ' damage"}, {"subject": "diabetes", "relation": "causes", "object":'
        ' "hair loss", "evidence": "diabetes causes hair loss"}]}'
    )
    report = graph.extract(settings, FakeModel(reply))
    assert sum(row["kept"] for row in report) >= 1
    assert sum(row["rejected"] for row in report) >= 1
    objects = {edge["object"] for edge in store.edges(settings)}
    assert "nerve damage" in objects and "hair loss" not in objects
    assert graph.extract(settings, FakeModel(reply)) == []  # nothing left to process


# ---------------------------------------------------------------- pipeline


def prepared(settings):
    database.initialize(settings)
    store.initialize(settings)
    run_import(settings)
    graph.extract(
        settings,
        FakeModel(
            '{"relationships": [{"subject": "high blood sugar", "relation": "causes",'
            ' "object": "kidney disease", "evidence": "high blood sugar can cause'
            ' nerve damage and kidney disease"}]}'
        ),
    )


def test_answer_cites_retrieved_passages_and_saves_the_trace(settings):
    prepared(settings)
    model = FakeModel()
    trace_id = pipeline.ask(
        settings, "What are symptoms of diabetes?", FakeEmbedder(), model
    )
    record = store.query(settings, trace_id)
    assert record["outcome"] == "answered"
    assert record["trace"]["passages"][0]["source_id"] == "mlp-a"
    assert record["trace"]["citations"]["cited"] == ["S1"]
    sent = model.calls[0]["messages"][1]["content"]
    assert "[S1] Diabetes (https://medlineplus.gov/a.html)" in sent
    assert record["trace"]["context"] in sent


def test_graph_adds_facts_about_entities_named_in_the_question(settings):
    prepared(settings)
    trace_id = pipeline.ask(
        settings,
        "What problems are linked to high blood sugar?",
        FakeEmbedder(),
        FakeModel("It can cause kidney disease. [G1]"),
    )
    facts = store.query(settings, trace_id)["trace"]["facts"]
    assert facts[0]["object"] == "kidney disease"
    assert facts[0]["via"] == "question"


def test_emergency_question_never_reaches_retrieval_or_the_model(settings):
    prepared(settings)
    model = FakeModel()
    record = store.query(
        settings,
        pipeline.ask(settings, "Am I having a heart attack?", FakeEmbedder(), model),
    )
    assert record["outcome"] == "emergency"
    assert "911" in record["answer"]
    assert model.calls == []


def test_low_score_or_model_refusal_gives_an_honest_not_covered(settings):
    prepared(settings)
    model = FakeModel()
    record = store.query(
        settings, pipeline.ask(settings, "Best pizza toppings?", FakeEmbedder(), model)
    )
    assert record["outcome"] == "not_covered" and model.calls == []
    refusing = FakeModel(pipeline.NOT_COVERED)
    record = store.query(
        settings,
        pipeline.ask(
            settings, "Symptoms of diabetes in cats?", FakeEmbedder(), refusing
        ),
    )
    assert record["outcome"] == "not_covered"
    assert record["answer"] == pipeline.NOT_COVERED_REPLY


def test_invented_citation_ids_are_flagged():
    passages = [{"id": "x"}]
    assert pipeline.citations("Yes [S1] [S7] [G2]", passages, []) == {
        "cited": ["S1"],
        "unknown": ["G2", "S7"],
    }


# ------------------------------------------------------------------ routes


def member(client, username="learner"):
    token = client.get("/api/csrf").json()["csrf_token"]
    body = {"username": username, "password": PASSWORD}
    client.post("/api/signup", json=body, headers={"X-CSRF-Token": token})
    client.post("/api/login", json=body, headers={"X-CSRF-Token": token})


def form_token(client):
    return re.search(
        r'name="csrf_token" value="([^"]+)"', client.get("/rag").text
    ).group(1)


def use_fakes(client, model=None):
    client.app.state.rag_embedder = FakeEmbedder()
    client.app.state.rag_model = model or FakeModel()


def test_visitors_see_sources_but_must_log_in_to_ask(client, settings):
    run_import(settings)
    page = client.get("/rag")
    assert page.status_code == 200 and "Log in to ask" in page.text
    assert "Not medical advice" in page.text
    record = client.get("/rag/sources")
    assert "mlp-a" in record.text and "fake-hash-64" in record.text
    token = client.get("/api/csrf").json()["csrf_token"]
    response = client.post(
        "/rag/ask",
        data={"question": "symptoms?", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303 and response.headers["location"] == "/login"


def test_member_question_shows_an_answer_trace_only_to_its_owner(client, settings):
    prepared(settings)
    member(client)
    use_fakes(client)
    response = client.post(
        "/rag/ask",
        data={
            "question": "What are symptoms of diabetes?",
            "csrf_token": form_token(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    trace = client.get(location)
    assert trace.status_code == 200
    assert "Thirst is a common symptom. [S1]" in trace.text
    assert "https://medlineplus.gov/a.html" in trace.text
    client.post("/logout", data={"csrf_token": form_token(client)})
    member(client, "someone_else")
    assert client.get(location).status_code == 404


def test_ask_requires_csrf_and_rejects_empty_questions(client, settings):
    prepared(settings)
    member(client)
    use_fakes(client)
    assert client.post("/rag/ask", data={"question": "symptoms?"}).status_code == 403
    empty = client.post(
        "/rag/ask", data={"question": " ", "csrf_token": form_token(client)}
    )
    assert empty.status_code == 422


def test_provider_failure_shows_a_safe_message(client, settings):
    prepared(settings)
    member(client)

    class Broken(FakeModel):
        def complete(self, messages, json_mode=False):
            raise RuntimeError("secret-key-123 rejected")

    use_fakes(client, Broken())
    response = client.post(
        "/rag/ask",
        data={
            "question": "What are symptoms of diabetes?",
            "csrf_token": form_token(client),
        },
    )
    assert response.status_code == 503
    assert "secret-key-123" not in response.text


def test_groq_waits_and_retries_when_rate_limited(monkeypatch):
    """A 429 from the free tier is retried instead of failing the import."""
    from app.rag import providers  # pylint: disable=import-outside-toplevel

    replies = [
        providers.httpx.Response(429, headers={"retry-after": "0"}),
        providers.httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        ),
    ]
    sent = []

    def fake_post(url, **kwargs):
        sent.append(kwargs["headers"]["Authorization"])
        response = replies.pop(0)
        response.request = providers.httpx.Request("POST", url)
        return response

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setattr(providers.time, "sleep", lambda seconds: None)
    assert providers.GroqChat(api_key="test-key").complete([]) == "ok"
    assert len(sent) == 2
