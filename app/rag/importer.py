"""Extract -> transform -> load for the MedlinePlus diabetes summaries.

Only the public-domain topic *summary* is imported, through MedlinePlus's own
developer web service. A.D.A.M. encyclopedia text, drug monographs and images
are never fetched.
"""

from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Callable
from xml.etree import ElementTree

import httpx

from app.rag import store
from app.settings import Settings

MANIFEST = Path(__file__).with_name("sources.json")
SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
MAX_CHUNK = 700
BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "ul", "ol", "div", "br"}


class _TextBlocks(HTMLParser):
    """Turn summary HTML into a list of paragraphs, keeping list items apart."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._current: list[str] = []
        self._in_item = False

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._current)).strip()
        if text:
            self.blocks.append(("• " if self._in_item else "") + text)
        self._current = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKS:
            self._flush()
        if tag == "li":
            self._in_item = True

    def handle_endtag(self, tag):
        if tag in BLOCKS:
            self._flush()
        if tag == "li":
            self._in_item = False

    def handle_data(self, data):
        self._current.append(data)

    def close(self):
        super().close()
        self._flush()


def paragraphs(summary_html: str) -> list[str]:
    """Plain-text paragraphs from MedlinePlus summary HTML."""
    parser = _TextBlocks()
    parser.feed(summary_html)
    parser.close()
    return parser.blocks


def chunk(blocks: list[str], limit: int = MAX_CHUNK) -> list[str]:
    """Group paragraphs into chunks of at most ``limit`` characters.

    Paragraph boundaries are kept: a chunk never ends in the middle of a sentence
    unless a single paragraph is longer than the limit. A paragraph ending in ':'
    (an intro to a list) stays with the list that follows it.
    """
    pieces: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > limit:
            sentences = re.split(r"(?<=[.!?])\s+", block)
        else:
            sentences = [block]
        for piece in sentences:
            joined = f"{current}\n{piece}" if current else piece
            if current and len(joined) > limit and not current.endswith(":"):
                pieces.append(current)
                current = piece
            else:
                current = joined
    if current:
        pieces.append(current)
    return pieces


def parse_search(xml_text: str, url: str) -> tuple[str, str]:
    """Find the document for ``url`` in a web-service reply: (title, summary HTML)."""
    root = ElementTree.fromstring(xml_text)
    for document in root.iter("document"):
        if document.get("url", "").rstrip("/") != url.rstrip("/"):
            continue
        fields = {
            item.get("name"): "".join(item.itertext())
            for item in document.findall("content")
        }
        summary = fields.get("FullSummary", "")
        title = re.sub(r"<[^>]+>", "", fields.get("title", ""))
        if summary:
            return title, summary
    raise LookupError(f"MedlinePlus web service returned no summary for {url}")


def fetch_summary(source: dict, client: httpx.Client) -> str:
    """Ask MedlinePlus's web service for one topic's summary HTML."""
    response = client.get(
        SEARCH_URL,
        params={"db": "healthTopics", "term": source["title"], "retmax": 20},
        timeout=20,
    )
    response.raise_for_status()
    return parse_search(response.text, source["url"])[1]


def load_manifest(path: Path = MANIFEST) -> dict:
    """The permitted source list, with its permission note."""
    return json.loads(path.read_text(encoding="utf-8"))


def import_sources(
    settings: Settings,
    embed: Callable[[list[str]], list[list[float]]],
    embed_model: str,
    fetch: Callable[[dict], str],
    manifest: dict | None = None,
) -> list[dict]:
    """Import every manifest source. Unchanged sources are skipped, not duplicated."""
    manifest = manifest or load_manifest()
    report = []
    for source in manifest["sources"]:
        summary_html = fetch(source)
        texts = chunk(paragraphs(summary_html))
        digest = sha256("\n\n".join(texts).encode("utf-8")).hexdigest()
        if store.source_hash(settings, source["id"]) == digest:
            report.append({"id": source["id"], "status": "unchanged"})
            continue
        vectors = embed([f"{source['title']}\n{text}" for text in texts])
        rows = [
            {
                "id": f"{source['id']}#c{position}-{digest[:8]}",
                "position": position,
                "text": text,
                "embedding": vector,
                "embed_model": embed_model,
            }
            for position, (text, vector) in enumerate(zip(texts, vectors))
        ]
        record = {**source, "permission": manifest["permission"]}
        store.replace_source(settings, {**record, "content_hash": digest}, rows)
        report.append({"id": source["id"], "status": "imported", "chunks": len(rows)})
    return report
