"""RAG pages: ask a question (members), read its trace (owner), see the sources.

Asking needs a signed-in member and a CSRF token, and is limited per hour, so a
public demo cannot run up the model bill. Import is not a web route at all.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app import security
from app.features.accounts import _page
from app.rag import pipeline, store

router = APIRouter()

HOURLY_LIMIT = 20
MAX_QUESTION = 300


def _services(request: Request):
    """The embedder and chat model, created on first use and then reused."""
    state = request.app.state
    if state.rag_embedder is None:
        state.rag_embedder = state.rag_factory["embedder"]()
    if state.rag_model is None:
        state.rag_model = state.rag_factory["model"]()
    return state.rag_embedder, state.rag_model


@router.get("/rag", include_in_schema=False)
def rag_home(request: Request):
    """Explain the app and show the question form to signed-in members."""
    user = security.authenticate(request)
    sources = store.summary(request.app.state.settings)
    return _page(request, "rag.html", user=user, sources=sources)


@router.post("/rag/ask", include_in_schema=False)
def rag_ask(request: Request, question: str = Form(""), csrf_token: str = Form("")):
    """Run one question through retrieval and generation, then show its trace."""
    security.require_csrf(request, csrf_token)
    user = security.authenticate(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    sources = store.summary(settings)
    question = question.strip()
    if not 3 <= len(question) <= MAX_QUESTION:
        return _page(
            request,
            "rag.html",
            422,
            user=user,
            sources=sources,
            error=f"Ask a question between 3 and {MAX_QUESTION} characters.",
        )
    if store.recent_count(settings, user["id"], 3600) >= HOURLY_LIMIT:
        return _page(
            request,
            "rag.html",
            429,
            user=user,
            sources=sources,
            error=f"You've asked {HOURLY_LIMIT} questions this hour. Try again later.",
        )
    try:
        embedder, model = _services(request)
        trace_id = pipeline.ask(settings, question, embedder, model, user["id"])
    except Exception:  # pylint: disable=broad-exception-caught
        # Provider errors can include request details; never echo them to visitors.
        return _page(
            request,
            "rag.html",
            503,
            user=user,
            sources=sources,
            error="The answer service is unavailable right now. Please try again.",
        )
    return RedirectResponse(f"/rag/trace/{trace_id}", status_code=303)


@router.get("/rag/trace/{trace_id}", include_in_schema=False)
def rag_trace(request: Request, trace_id: str):
    """Show one answer with everything retrieved for it, to its owner only."""
    user = security.authenticate(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    record = store.query(request.app.state.settings, trace_id)
    if record is None or record["user_id"] != user["id"]:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return _page(request, "rag_trace.html", user=user, record=record)


@router.get("/rag/sources", include_in_schema=False)
def rag_sources(request: Request):
    """Public import record: every source, its counts and a sample representation."""
    settings = request.app.state.settings
    rows = store.chunks(settings)
    sample = rows[0] if rows else None
    return _page(
        request,
        "rag_sources.html",
        sources=store.summary(settings),
        sample=sample,
        dimensions=len(sample["embedding"]) if sample else 0,
        preview=(
            [round(value, 4) for value in sample["embedding"][:8]] if sample else []
        ),
        edges=store.edges(settings)[:12],
    )


@router.get("/api/rag/sources")
def api_rag_sources(request: Request) -> dict:
    """The same import record as JSON."""
    return {"sources": store.summary(request.app.state.settings)}
