"""Trusted command line for the RAG app (run on the laptop or server, not the web).

python -m app.rag import     # fetch MedlinePlus summaries, chunk, embed, store
python -m app.rag graph      # extract relationships and check each one
python -m app.rag ask "What are common diabetes symptoms?"
python -m app.rag report     # sources, counts and a sample chunk/edges
"""

import argparse
import json
import sys

import httpx

from app import database
from app.rag import graph, importer, pipeline, providers, store
from app.settings import Settings


def _print(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    """Run one RAG maintenance command."""
    parser = argparse.ArgumentParser(prog="python -m app.rag")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("import", help="import the permitted MedlinePlus sources")
    commands.add_parser("graph", help="extract and check relationships")
    asker = commands.add_parser("ask", help="ask one question and print its trace")
    asker.add_argument("question")
    commands.add_parser("report", help="print the import record and a sample")
    args = parser.parse_args(argv)

    settings = Settings.load()
    database.initialize(settings)
    store.initialize(settings)

    if args.command == "import":
        embedder = providers.FastEmbedder()
        with httpx.Client(headers={"User-Agent": "is373-student-rag"}) as client:
            report = importer.import_sources(
                settings,
                embedder.embed,
                embedder.model,
                lambda source: importer.fetch_summary(source, client),
            )
        _print(report)
    elif args.command == "graph":
        _print(graph.extract(settings, providers.groq_from_environment()))
    elif args.command == "ask":
        trace_id = pipeline.ask(
            settings,
            args.question,
            providers.FastEmbedder(),
            providers.groq_from_environment(),
        )
        _print(store.query(settings, trace_id))
    else:
        rows = store.chunks(settings)
        sample = rows[0] if rows else None
        if sample:
            sample = {**sample, "embedding": sample["embedding"][:8] + ["..."]}
        _print(
            {
                "sources": store.summary(settings),
                "sample_chunk": sample,
                "sample_edges": store.edges(settings)[:5],
            }
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
