"""SQLite-Schema und Hilfsfunktionen.

Vertrauensstufen werden in getrennten Tabellen gehalten:
  Quelldaten        documents, document_versions, paragraphs, spans, links
  Fremdcodes        upstream_codes (historische Klassifikation des Ausgangsprojekts, nicht neu geprüft)
  Maschine          claim_candidates, relation_hypotheses (immer mit run_id)
  Mensch            reviews (append-only), relation_hypotheses mit kind='manual'
  Formale Prüfung   quote_check_json an jeder Interpretation
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

DB_SCHEMA_VERSION = 3

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS import_runs (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,                 -- upstream_json | upstream_csv | synthetic_fixtures | manual_text
  source_url TEXT, source_path TEXT, sha256 TEXT,
  upstream_commit TEXT, license TEXT, notes TEXT,
  started_at TEXT NOT NULL, finished_at TEXT,
  n_records INTEGER, n_new INTEGER, n_updated INTEGER, n_unchanged INTEGER,
  report_json TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,                -- z. B. upstream:mc-lit-review:post:123 | synthetic:case01:A
  origin TEXT NOT NULL,               -- upstream_json | upstream_csv | synthetic | manual
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  upstream_ns TEXT, upstream_id TEXT,
  canonical_url TEXT, host TEXT, slug TEXT,
  title TEXT, subtitle TEXT, author TEXT, publication TEXT, date TEXT,
  upstream_words INTEGER, upstream_paywalled INTEGER,
  upstream_payload TEXT,              -- unveränderter Originaldatensatz inkl. unbekannter Felder
  payload_sha256 TEXT,
  import_run_id INTEGER REFERENCES import_runs(id),
  first_seen_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (upstream_ns, upstream_id)
);
CREATE INDEX IF NOT EXISTS ix_documents_url ON documents(canonical_url);

CREATE TABLE IF NOT EXISTS upstream_codes (
  document_id TEXT PRIMARY KEY REFERENCES documents(id),
  import_run_id INTEGER REFERENCES import_runs(id),
  codebook_version TEXT,
  relevance TEXT, genre TEXT, claim_object TEXT, community TEXT, grp TEXT,
  experience_now TEXT, cognition_now TEXT, agency_now TEXT, possible TEXT, moral_status TEXT, serious TEXT,
  axes_source TEXT,
  csv_display_json TEXT,              -- CSV-Anzeigebezeichnungen, nicht als interne Codes behandelt
  arguments_json TEXT, features_json TEXT, stance_json TEXT,
  view_revised TEXT, cluster_label TEXT, quarter TEXT
);

CREATE TABLE IF NOT EXISTS document_versions (
  id INTEGER PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id),
  fetched_at TEXT NOT NULL,
  source TEXT NOT NULL,               -- substack_api | manual_file | synthetic_fixture
  source_url TEXT,
  http_status INTEGER,
  raw_path TEXT, raw_sha256 TEXT,
  text_path TEXT, text_sha256 TEXT, n_chars INTEGER, n_words INTEGER,
  status TEXT NOT NULL,               -- siehe fetch.STATUSES
  availability TEXT NOT NULL,         -- full | partial | preview | unavailable
  status_detail TEXT,
  language TEXT,
  is_current INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_versions_doc ON document_versions(document_id);

CREATE TABLE IF NOT EXISTS paragraphs (
  version_id INTEGER NOT NULL REFERENCES document_versions(id),
  idx INTEGER NOT NULL,
  start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
  kind TEXT NOT NULL,                 -- p | h | blockquote | li | pre | caption | footnote
  speaker_hint TEXT,                  -- heuristisch: author | quoted_other | unclear
  PRIMARY KEY (version_id, idx)
);

CREATE TABLE IF NOT EXISTS spans (
  id TEXT PRIMARY KEY,
  version_id INTEGER NOT NULL REFERENCES document_versions(id),
  start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
  text TEXT NOT NULL,
  paragraph_idx INTEGER,
  speaker TEXT,
  origin TEXT NOT NULL,               -- quote_heuristic | model_quote | manual
  text_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_spans_version ON spans(version_id);

CREATE TABLE IF NOT EXISTS links (
  version_id INTEGER NOT NULL REFERENCES document_versions(id),
  start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
  href TEXT NOT NULL, target TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_links_target ON links(target);

CREATE TABLE IF NOT EXISTS argument_units (
  id TEXT PRIMARY KEY,                -- <version_id>:<method_version>:<seq>
  version_id INTEGER NOT NULL REFERENCES document_versions(id),
  document_id TEXT NOT NULL REFERENCES documents(id),
  seq INTEGER NOT NULL,
  start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
  para_start INTEGER, para_end INTEGER,
  ctx_start INTEGER, ctx_end INTEGER,
  n_tokens INTEGER, token_counter TEXT,
  heading TEXT,
  text TEXT NOT NULL,
  method TEXT NOT NULL, method_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_units_version ON argument_units(version_id);
CREATE INDEX IF NOT EXISTS ix_units_doc ON argument_units(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS units_fts USING fts5(unit_id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2');

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,                 -- fetch | segment | embed | search | reconstruct | compare | countercheck | acceptance
  code_version TEXT, adapter TEXT, model TEXT, prompt_version TEXT,
  is_real_model_run INTEGER NOT NULL DEFAULT 0,
  is_dry_run INTEGER NOT NULL DEFAULT 0,
  config_json TEXT, input_hashes_json TEXT,
  started_at TEXT NOT NULL, finished_at TEXT,
  status TEXT, error TEXT, usage_json TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS embedding_sets (
  id TEXT PRIMARY KEY,
  backend TEXT NOT NULL, model_id TEXT, model_revision TEXT,
  is_test_vectors INTEGER NOT NULL,
  dim INTEGER, n_vectors INTEGER, dir TEXT NOT NULL,
  manifest_json TEXT, run_id TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_comparisons (
  id TEXT PRIMARY KEY,
  left_unit_id TEXT NOT NULL REFERENCES argument_units(id),
  right_unit_id TEXT NOT NULL REFERENCES argument_units(id),
  channels_json TEXT NOT NULL,        -- Suchwege, über die das Paar gefunden wurde
  scores_json TEXT,
  markers_json TEXT,                  -- deterministische Unterschiedshinweise (keine Interpretation)
  temporal TEXT,                      -- right_later | right_earlier | same_date | undated
  shared_question TEXT,
  search_run_id TEXT REFERENCES runs(id),
  corpus_scope_json TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (left_unit_id, right_unit_id)
);

CREATE TABLE IF NOT EXISTS claim_candidates (
  id TEXT PRIMARY KEY,
  unit_id TEXT NOT NULL REFERENCES argument_units(id),
  run_id TEXT NOT NULL REFERENCES runs(id),
  status TEXT NOT NULL,               -- ok | quote_unverified | insufficient_context | parse_error | model_error
  payload_json TEXT, quote_check_json TEXT, raw_response_path TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relation_hypotheses (
  id TEXT PRIMARY KEY,
  comparison_id TEXT NOT NULL REFERENCES candidate_comparisons(id),
  run_id TEXT REFERENCES runs(id),    -- NULL bei manueller Annotation
  kind TEXT NOT NULL,                 -- model_primary | model_countercheck | manual
  parent_id TEXT REFERENCES relation_hypotheses(id),
  author TEXT,
  status TEXT NOT NULL,
  relation_types_json TEXT,
  payload_json TEXT, quote_check_json TEXT, raw_response_path TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rel_comp ON relation_hypotheses(comparison_id);

CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY,
  target_type TEXT NOT NULL,          -- relation_hypothesis | claim_candidate | comparison
  target_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  decision TEXT NOT NULL,             -- confirmed | corrected | rejected | undecidable
  comment TEXT, corrected_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS reviews_no_update BEFORE UPDATE ON reviews
  BEGIN SELECT RAISE(ABORT, 'reviews sind append-only'); END;
CREATE TRIGGER IF NOT EXISTS reviews_no_delete BEFORE DELETE ON reviews
  BEGIN SELECT RAISE(ABORT, 'reviews sind append-only'); END;

CREATE TABLE IF NOT EXISTS model_budgets (
  id TEXT PRIMARY KEY,                -- ausdrücklich angelegter Lauf mit gemeinsamem Aufrufbudget
  label TEXT NOT NULL,
  max_calls INTEGER NOT NULL,
  adapter TEXT, model TEXT,
  created_at TEXT NOT NULL, closed_at TEXT, notes TEXT
);

-- Jeder Aufrufversuch (auch Fehler und Wiederholungen) wird VOR dem Aufruf eingetragen und zählt.
-- Abgelehnte Versuche (Budget erschöpft) werden mit outcome='refused_budget' protokolliert und zählen nicht.
CREATE TABLE IF NOT EXISTS model_calls (
  id INTEGER PRIMARY KEY,
  budget_id TEXT REFERENCES model_budgets(id),
  run_id TEXT,
  attempt INTEGER NOT NULL,           -- 1 = Erstversuch, 2.. = Wiederholung innerhalb desselben Laufs
  adapter TEXT NOT NULL, model_requested TEXT, model_reported TEXT,
  is_real_service INTEGER NOT NULL,
  purpose TEXT,
  est_input_tokens INTEGER, max_output_tokens INTEGER,
  started_at TEXT NOT NULL, finished_at TEXT,
  outcome TEXT NOT NULL,              -- started | success | error | refused_budget
  error TEXT, usage_json TEXT, raw_path TEXT
);
CREATE INDEX IF NOT EXISTS ix_calls_budget ON model_calls(budget_id);

CREATE TABLE IF NOT EXISTS reading_aids (
  id INTEGER PRIMARY KEY,
  unit_id TEXT NOT NULL REFERENCES argument_units(id),
  lang TEXT NOT NULL,
  text TEXT NOT NULL,
  author TEXT NOT NULL,               -- wer die Lesehilfe erstellt hat
  method TEXT NOT NULL,               -- z. B. 'sinngemäße Zusammenfassung, ungeprüft'
  source_text_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_sets (
  id TEXT PRIMARY KEY, label TEXT NOT NULL, method_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_set_items (
  set_id TEXT NOT NULL REFERENCES review_sets(id),
  position INTEGER NOT NULL,
  comparison_id TEXT NOT NULL REFERENCES candidate_comparisons(id),
  search_hypothesis TEXT NOT NULL,    -- Suchhypothese der Auswahl, KEINE richtige Antwort
  selection_reason TEXT,
  PRIMARY KEY (set_id, position)
);

-- Übersetzungen der angezeigten Textauswahl. Verankert an Dokument, Textversion (Hash) und Zeichenbereich;
-- source_sha256 ist der Hash des übersetzten Originalsegments. Inhalte bleiben lokal (fremde Texte).
CREATE TABLE IF NOT EXISTS translations (
  id INTEGER PRIMARY KEY,
  translation_set TEXT NOT NULL, lang TEXT NOT NULL,
  document_id TEXT NOT NULL, version_text_sha256 TEXT NOT NULL,
  start_char INTEGER NOT NULL, end_char INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
  text TEXT NOT NULL, notes_json TEXT,
  method TEXT NOT NULL, created_by TEXT NOT NULL, review_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (translation_set, document_id, start_char, end_char, source_sha256)
);

-- Blindurteile: append-only. stage = free (erstes freies Urteil) | labels | amendment | correction | reveal
CREATE TABLE IF NOT EXISTS blind_judgments (
  id INTEGER PRIMARY KEY,
  set_id TEXT NOT NULL, position INTEGER NOT NULL, comparison_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  stage TEXT NOT NULL,
  parent_id INTEGER REFERENCES blind_judgments(id),
  verdict TEXT,                       -- difference | no_relevant_difference | undecidable
  answers_json TEXT, relation_types_json TEXT, flags_json TEXT, quote_check_json TEXT,
  revealed_before INTEGER NOT NULL DEFAULT 0,
  source_state_json TEXT,             -- Hashes der angezeigten Originale und Übersetzungen zum Zeitpunkt des Urteils
  origin TEXT NOT NULL DEFAULT 'web', -- web | html_import
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_blind ON blind_judgments(set_id, position, reviewer);
CREATE TRIGGER IF NOT EXISTS blind_no_update BEFORE UPDATE ON blind_judgments
  BEGIN SELECT RAISE(ABORT, 'blind_judgments sind append-only'); END;
CREATE TRIGGER IF NOT EXISTS blind_no_delete BEFORE DELETE ON blind_judgments
  BEGIN SELECT RAISE(ABORT, 'blind_judgments sind append-only'); END;

CREATE TABLE IF NOT EXISTS revisions (
  id INTEGER PRIMARY KEY,
  entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  before_json TEXT, change_json TEXT, reason TEXT, author TEXT,
  created_at TEXT NOT NULL
);
"""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    cur = conn.execute("SELECT value FROM meta WHERE key='db_schema_version'").fetchone()
    if cur is None or cur[0] != str(DB_SCHEMA_VERSION):
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('db_schema_version', ?)", (str(DB_SCHEMA_VERSION),))
    conn.commit()
    return conn


MIGRATIONS = {
    "runs": [("budget_id", "TEXT")],
    # Getrennte Prüfebenen (Schema v2): Antwort empfangen / Schema gültig / Anker geprüft / Modellurteil
    "relation_hypotheses": [("response_status", "TEXT"), ("schema_status", "TEXT"), ("schema_errors_json", "TEXT"),
                            ("anchor_status", "TEXT"), ("judgment", "TEXT"), ("evidence_status", "TEXT")],
    "review_sets": [("version", "INTEGER"), ("supersedes", "TEXT"), ("change_reason", "TEXT"), ("items_sha256", "TEXT")],
    "claim_candidates": [("response_status", "TEXT"), ("schema_status", "TEXT"), ("schema_errors_json", "TEXT"),
                         ("anchor_status", "TEXT"), ("judgment", "TEXT"), ("evidence_status", "TEXT")],
}


def _migrate(conn) -> None:
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def add_revision(conn, entity_type: str, entity_id: str, before, change, reason: str, author: str) -> None:
    conn.execute(
        "INSERT INTO revisions(entity_type, entity_id, before_json, change_json, reason, author, created_at) VALUES(?,?,?,?,?,?,?)",
        (entity_type, entity_id, dumps(before) if before is not None else None, dumps(change), reason, author, now()),
    )


def new_run_id(kind: str) -> str:
    import uuid
    return f"{kind}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
