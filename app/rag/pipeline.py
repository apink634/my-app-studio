"""Question -> safety check -> vector + graph retrieval -> cited answer -> trace."""

import os
import re

from app.rag import store
from app.rag.providers import ChatModel, Embedder
from app.settings import Settings

TOP_K = 4
MAX_FACTS = 8
MIN_SCORE = float(os.environ.get("RAG_MIN_SCORE", "0.6"))
NOT_COVERED = "NOT_COVERED"

EMERGENCY = re.compile(
    r"heart attack|chest pain|can'?t breathe|cannot breathe|trouble breathing|"
    r"stroke|unconscious|passed out|seizure|overdose|suicid|kill myself",
    re.IGNORECASE,
)
EMERGENCY_REPLY = (
    "This sounds like it could be an emergency. This app can't diagnose you. "
    "Call 911 (or your local emergency number) now."
)
NOT_COVERED_REPLY = (
    "My MedlinePlus sources don't cover that, so I won't guess. "
    "Try asking a doctor, nurse or pharmacist."
)
SYSTEM = (
    "You answer questions about diabetes for someone who is learning about it. "
    "Use ONLY the numbered sources below. After each sentence, cite the source "
    "ids it comes from, like [S1] or [G2]. If the sources do not answer the "
    f"question, reply with exactly {NOT_COVERED}. Do not diagnose, do not give "
    "personal dosing or treatment advice, and remind the reader to talk with "
    "their care team. Keep the answer under 150 words."
)


def _terms(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def vector_search(question_vector: list[float], rows: list[dict]) -> list[dict]:
    """Rank chunks by cosine similarity (vectors are already normalized)."""
    scored = [
        {
            **{key: row[key] for key in ("id", "source_id", "text", "title", "url")},
            "score": round(
                sum(a * b for a, b in zip(question_vector, row["embedding"])), 4
            ),
        }
        for row in rows
    ]
    return sorted(scored, key=lambda row: row["score"], reverse=True)[:TOP_K]


def graph_search(
    question: str, passages: list[dict], all_edges: list[dict]
) -> list[dict]:
    """Facts about entities named in the question, then facts from the top passages.

    Following an entity across every page is what vector search alone cannot do:
    "high blood sugar -> causes -> nerve damage" may sit on a different page
    from the passage that best matches the question.
    """
    words = f" {_terms(question)} "
    named = {
        name
        for edge in all_edges
        for name in (edge["subject"], edge["object"])
        if f" {_terms(name).strip()} " in words
    }
    top_chunks = {passage["id"] for passage in passages}
    first = [e for e in all_edges if e["subject"] in named or e["object"] in named]
    second = [e for e in all_edges if e["chunk_id"] in top_chunks and e not in first]
    facts = (first + second)[:MAX_FACTS]
    return [
        {
            key: edge[key]
            for key in ("id", "subject", "relation", "object", "chunk_id", "evidence")
        }
        | {
            "title": edge["title"],
            "url": edge["url"],
            "via": "question" if edge in first else "passage",
        }
        for edge in facts
    ]


def build_context(passages: list[dict], facts: list[dict]) -> str:
    """The exact text sent to the model, with an id for every piece."""
    lines = []
    for number, passage in enumerate(passages, 1):
        lines.append(
            f"[S{number}] {passage['title']} ({passage['url']})\n{passage['text']}"
        )
    for number, fact in enumerate(facts, 1):
        lines.append(
            f"[G{number}] {fact['subject']} {fact['relation'].replace('_', ' ')} "
            f"{fact['object']}. Evidence: \"{fact['evidence']}\" ({fact['url']})"
        )
    return "\n\n".join(lines)


def citations(answer: str, passages: list[dict], facts: list[dict]) -> dict:
    """Which source ids the answer cited, and any it cited that do not exist."""
    cited = sorted(set(re.findall(r"\[([SG]\d+)\]", answer)))
    known = {f"S{n}" for n in range(1, len(passages) + 1)}
    known |= {f"G{n}" for n in range(1, len(facts) + 1)}
    return {
        "cited": [item for item in cited if item in known],
        "unknown": [item for item in cited if item not in known],
    }


def _save(
    settings, user_id, question, outcome, trace, answer
):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    return store.save_query(
        settings,
        {
            "user_id": user_id,
            "question": question,
            "outcome": outcome,
            "trace": trace,
            "answer": answer,
        },
    )


def ask(
    settings: Settings,
    question: str,
    embedder: Embedder,
    model: ChatModel,
    user_id: str | None = None,
) -> str:
    """Answer one question and save its full trace. Returns the trace id."""
    question = question.strip()
    trace: dict = {
        "embed_model": embedder.model,
        "chat_model": None,
        "min_score": MIN_SCORE,
    }
    if EMERGENCY.search(question):
        trace["guard"] = "emergency words matched; no retrieval or model call"
        return _save(settings, user_id, question, "emergency", trace, EMERGENCY_REPLY)
    rows = store.chunks(settings)
    passages = vector_search(embedder.embed([question])[0], rows) if rows else []
    trace["passages"] = passages
    if not passages or passages[0]["score"] < MIN_SCORE:
        trace["guard"] = "best passage below the minimum score; model not called"
        return _save(
            settings, user_id, question, "not_covered", trace, NOT_COVERED_REPLY
        )
    facts = graph_search(question, passages, store.edges(settings))
    context = build_context(passages, facts)
    trace |= {"facts": facts, "context": context, "chat_model": model.model}
    answer = model.complete(
        [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Sources:\n\n{context}\n\nQuestion: {question}",
            },
        ]
    ).strip()
    trace["raw_answer"] = answer
    if NOT_COVERED in answer:
        return _save(
            settings, user_id, question, "not_covered", trace, NOT_COVERED_REPLY
        )
    trace["citations"] = citations(answer, passages, facts)
    outcome = "answered" if trace["citations"]["cited"] else "answered_uncited"
    return _save(settings, user_id, question, outcome, trace, answer)
