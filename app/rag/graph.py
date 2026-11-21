"""Entity/relationship extraction with a source check on every relationship.

The model proposes relationships and must quote the sentence that states each
one. A relationship is kept only if that quote really appears in the chunk and
both entities are named in it. Anything else is counted as rejected, because
AI extraction can invent links that the source never states.
"""

import json
import re

from app.rag import store
from app.rag.providers import ChatModel
from app.settings import Settings

RELATIONS = {
    "has_symptom",
    "causes",
    "risk_factor_for",
    "complication_of",
    "treated_by",
    "prevented_by",
    "diagnosed_by",
    "type_of",
}

PROMPT = (
    "Extract relationships from this MedlinePlus passage about diabetes.\n"
    "Use only these relations: {relations}.\n"
    "Each relationship needs: subject, relation, object, and evidence, where "
    "evidence is copied word for word from the passage and names both the "
    "subject and the object. Use short lowercase entity names that appear in "
    "the evidence. Do not add anything the passage does not state.\n"
    'Reply with JSON only: {{"relationships": [{{"subject": "...", '
    '"relation": "...", "object": "...", "evidence": "..."}}]}}\n\n'
    "Passage:\n{passage}"
)


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("•", " ")).strip().lower()


def check(candidate: dict, passage: str) -> dict | None:
    """Return a cleaned relationship if the passage supports it, else None."""
    try:
        subject = _plain(str(candidate["subject"]))
        relation = str(candidate["relation"]).strip().lower()
        obj = _plain(str(candidate["object"]))
        evidence = re.sub(r"\s+", " ", str(candidate["evidence"])).strip()
    except (KeyError, TypeError):
        return None
    plain_evidence = _plain(evidence)
    supported = (
        relation in RELATIONS
        and subject
        and obj
        and subject != obj
        and len(plain_evidence) >= 10
        and plain_evidence in _plain(passage)
        and subject in plain_evidence
        and obj in plain_evidence
    )
    if not supported:
        return None
    return {
        "subject": subject,
        "relation": relation,
        "object": obj,
        "evidence": evidence,
    }


def parse_reply(reply: str) -> list[dict]:
    """Read the model's JSON, tolerating text around the object."""
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    items = data.get("relationships", []) if isinstance(data, dict) else []
    return [item for item in items if isinstance(item, dict)]


def extract(settings: Settings, model: ChatModel) -> list[dict]:
    """Run extraction for every chunk that has not been processed yet."""
    report = []
    for row in store.chunks_without_graph(settings):
        reply = model.complete(
            [
                {
                    "role": "user",
                    "content": PROMPT.format(
                        relations=", ".join(sorted(RELATIONS)), passage=row["text"]
                    ),
                }
            ],
            json_mode=True,
        )
        candidates = parse_reply(reply)
        kept = []
        for candidate in candidates:
            edge = check(candidate, row["text"])
            if edge and edge not in kept:
                kept.append(edge)
        rejected = len(candidates) - len(kept)
        store.save_edges(settings, row["id"], kept, rejected, model.model)
        report.append({"chunk": row["id"], "kept": len(kept), "rejected": rejected})
    return report
