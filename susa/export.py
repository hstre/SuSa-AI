"""JSONL-Export eigener Ergebnisse mit Schema- und Versionsangaben.

Standardmäßig ohne fremde Volltexte: Einheiten und Spannen werden über Dokument-ID, Versions-Hash und
Zeichenpositionen referenziert. Kurze Belegzitate werden nur mit --include-quotes exportiert.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import SCHEMA_VERSION, db
from .config import code_version


def export_jsonl(conn, out: Path, include_quotes: bool = False, synthetic: bool | None = None) -> dict:
    n = {}

    def emit(f, kind, obj):
        f.write(json.dumps({"schema": SCHEMA_VERSION, "type": kind, **obj}, ensure_ascii=False) + "\n")
        n[kind] = n.get(kind, 0) + 1

    def keep(doc_synth: int) -> bool:
        return synthetic is None or bool(doc_synth) == synthetic

    with open(out, "w", encoding="utf-8") as f:
        emit(f, "header", {"code_version": code_version(), "exported_at": db.now(), "include_quotes": include_quotes,
                           "licenses": {"upstream_metadata": "CC BY 4.0, Mike Thicke, mc-lit-review (siehe NOTICE.md)",
                                        "article_texts": "nicht enthalten; Rechte bei den jeweiligen Autorinnen und Autoren"}})
        for r in conn.execute("SELECT * FROM import_runs"):
            emit(f, "import_run", {k: r[k] for k in ("id", "kind", "source_url", "sha256", "upstream_commit", "license", "started_at")})
        for d in conn.execute("SELECT * FROM documents WHERE id IN (SELECT document_id FROM document_versions)"):
            if keep(d["is_synthetic"]):
                emit(f, "document", {k: d[k] for k in ("id", "origin", "is_synthetic", "upstream_ns", "upstream_id", "canonical_url",
                                                       "title", "author", "publication", "date")})
        for v in conn.execute("SELECT v.*, d.is_synthetic FROM document_versions v JOIN documents d ON d.id=v.document_id"):
            if keep(v["is_synthetic"]):
                emit(f, "document_version", {k: v[k] for k in ("id", "document_id", "fetched_at", "source", "source_url", "text_sha256",
                                                               "n_chars", "status", "availability", "status_detail", "is_current")})
        for u in conn.execute("SELECT u.*, v.text_sha256, d.is_synthetic FROM argument_units u JOIN document_versions v ON v.id=u.version_id JOIN documents d ON d.id=u.document_id"):
            if keep(u["is_synthetic"]):
                o = {k: u[k] for k in ("id", "document_id", "version_id", "text_sha256", "start_char", "end_char", "n_tokens", "method", "method_version")}
                if include_quotes and u["is_synthetic"]:
                    o["text"] = u["text"]
                emit(f, "argument_unit", o)
        for c in conn.execute("SELECT * FROM candidate_comparisons"):
            emit(f, "candidate_comparison", {"id": c["id"], "left_unit_id": c["left_unit_id"], "right_unit_id": c["right_unit_id"],
                                              "retrieval_channels": json.loads(c["channels_json"]), "scores": json.loads(c["scores_json"] or "{}"),
                                              "markers": json.loads(c["markers_json"] or "[]"), "temporal": c["temporal"],
                                              "corpus_scope": json.loads(c["corpus_scope_json"] or "null"), "search_run_id": c["search_run_id"]})
        for h in conn.execute("SELECT h.*, r.adapter, r.model, r.prompt_version, r.is_real_model_run FROM relation_hypotheses h LEFT JOIN runs r ON r.id=h.run_id"):
            payload = json.loads(h["payload_json"] or "{}")
            qc = json.loads(h["quote_check_json"] or "{}")
            if not include_quotes:
                for k in ("left_quotes", "right_quotes"):
                    payload.pop(k, None)
                for side in ("left", "right"):
                    for q in qc.get(side, []) or []:
                        q.pop("quote", None)
            emit(f, "relation_hypothesis", {"id": h["id"], "comparison_id": h["comparison_id"], "kind": h["kind"], "parent_id": h["parent_id"],
                                             "status": h["status"], "relation_types": json.loads(h["relation_types_json"] or "[]"),
                                             "payload": payload, "quote_check": qc, "run": {"id": h["run_id"], "adapter": h["adapter"],
                                             "model": h["model"], "prompt_version": h["prompt_version"], "is_real_model_run": h["is_real_model_run"]},
                                             "author": h["author"], "created_at": h["created_at"],
                                             "confidence_is_calibrated_probability": False})
        for r in conn.execute("SELECT * FROM reviews ORDER BY id"):
            emit(f, "review", dict(r))
        for r in conn.execute("SELECT * FROM revisions ORDER BY id"):
            emit(f, "revision", dict(r))
        for r in conn.execute("SELECT id, kind, code_version, adapter, model, prompt_version, is_real_model_run, is_dry_run, started_at, finished_at, status, error, usage_json FROM runs"):
            emit(f, "run", dict(r))
    return n
