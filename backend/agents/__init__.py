"""
The team's agent implementations, one package per pipeline stage.

Each package is the code its owner wrote, moved here unchanged apart
from the import fixes needed to make it importable as a package. The
thin `Agent` subclasses the coordinator actually calls live in
`adapters.py`, so an owner can keep editing their own module without
touching orchestrator code.

  collection/     fetch, dedupe, relevance-filter and preprocess articles
  security/       sanitization filter (prompt injection, HTML, PII)
  classification/ stakeholder + source-type classifiers (keyword & LLM)
  topic/          BERTopic topic model - standalone script, not yet wired
                  into the pipeline (see docs/pipeline-coordinator.md)
"""
