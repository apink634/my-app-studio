"""Individual RAG app: MedlinePlus diabetes summaries -> chunks + graph -> answers.

Import is a trusted command-line step (``python -m app.rag import``); visitors can
only ask questions. Every answer keeps a trace of what was retrieved and sent.
"""
