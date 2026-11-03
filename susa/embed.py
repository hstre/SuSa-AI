"""Abschnittsweise Embeddings mit getrennter, reproduzierbarer Vektorablage.

Backends:
  onnx-bge-small  BAAI/bge-small-en-v1.5 als ONNX auf CPU, CLS-Pooling, L2-normalisiert (lokal, kostenlos)
  test-hash       deterministische Hash-Bag-of-Words-Testvektoren. KEINE semantische Suche; nur für Tests
                  und wenn kein Modell verfügbar ist. Wird in Oberfläche und Berichten sichtbar ausgewiesen.

Hinweis: bge-small-en-v1.5 ist ein englisches Modell. Deutsche Texte werden technisch eingebettet, die
semantische Nähe über Sprachgrenzen hinweg ist damit aber nicht belastbar (siehe Abnahmefall 3).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import requests

from . import db
from .config import Config, code_version
from .segment import METHOD_VERSION, model_dir

MODEL_FILES = {"onnx/model.onnx": "model.onnx", "tokenizer.json": "tokenizer.json", "config.json": "config.json"}
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def download_model(cfg: Config) -> dict:
    ec = cfg.section("embed")
    rev = ec["model_revision"]
    d = model_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    manifest = {"model_id": ec["model_id"], "revision": rev, "files": {}}
    for remote, local in MODEL_FILES.items():
        url = f"https://huggingface.co/{ec['model_id']}/resolve/{rev}/{remote}"
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        (d / local).write_bytes(r.content)
        manifest["files"][local] = {"url": url, "sha256": db.sha256_bytes(r.content), "bytes": len(r.content)}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return manifest


class OnnxBge:
    name = "onnx-bge-small"
    is_test = False

    def __init__(self, cfg: Config):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = model_dir(cfg)
        if not (d / "model.onnx").exists():
            raise FileNotFoundError(f"Modell fehlt in {d}. Erst `susa download-model` ausführen oder backend=test-hash wählen.")
        self.manifest = json.loads((d / "manifest.json").read_text("utf-8")) if (d / "manifest.json").exists() else {}
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(max_length=512)
        self.tok.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        self.sess = ort.InferenceSession(str(d / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.model_id = cfg.section("embed").get("model_id")
        self.revision = cfg.section("embed").get("model_revision")
        self.truncated = 0

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        out = []
        for i in range(0, len(texts), batch_size):
            enc = self.tok.encode_batch(texts[i:i + batch_size])
            self.truncated += sum(1 for e in enc if e.overflowing)
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.sess.run(None, feed)[0]
            cls = hidden[:, 0, :]
            out.append(cls / np.linalg.norm(cls, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32) if out else np.zeros((0, 384), np.float32)

    def encode_query(self, q: str) -> np.ndarray:
        return self.encode([QUERY_PREFIX + q])[0]


class HashVectors:
    """Deterministische Testvektoren (Feature-Hashing über Wörter und Wortpaare)."""
    name = "test-hash"
    is_test = True
    model_id = "test-hash-bow-256"
    revision = "1"
    truncated = 0
    manifest = {"hinweis": "Testvektoren, keine semantische Suche"}

    def __init__(self, cfg: Config | None = None, dim: int = 256):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, np.float32)
        toks = re.findall(r"\w+", text.lower())
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
        for f in feats:
            h = int.from_bytes(hashlib.sha1(f.encode()).digest()[:8], "little")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode(self, texts: list[str], batch_size: int = 0) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def encode_query(self, q: str) -> np.ndarray:
        return self._vec(q)


def get_backend(cfg: Config, name: str | None = None):
    name = name or cfg.section("embed").get("backend", "onnx-bge-small")
    if name == "test-hash":
        return HashVectors(cfg)
    if name == "onnx-bge-small":
        return OnnxBge(cfg)
    raise ValueError(f"unbekanntes Embedding-Backend {name}")


def set_id_for(backend) -> str:
    return f"{backend.name}-{str(backend.revision)[:8]}-{METHOD_VERSION}"


class VectorStore:
    def __init__(self, cfg: Config, set_id: str):
        self.dir = cfg.subdir(f"vectors/{set_id}")
        self.set_id = set_id
        self.ids: list[str] = []
        self.vecs = None
        if (self.dir / "unit_ids.json").exists():
            self.ids = json.loads((self.dir / "unit_ids.json").read_text("utf-8"))
            self.vecs = np.load(self.dir / "vectors.npy")
        self.index = {u: i for i, u in enumerate(self.ids)}

    def add(self, ids: list[str], vecs: np.ndarray):
        self.vecs = vecs if self.vecs is None else np.vstack([self.vecs, vecs])
        for u in ids:
            self.index[u] = len(self.ids)
            self.ids.append(u)

    def save(self, manifest: dict):
        np.save(self.dir / "vectors.npy", self.vecs)
        (self.dir / "unit_ids.json").write_text(json.dumps(self.ids), "utf-8")
        manifest = dict(manifest, n_vectors=len(self.ids), vectors_sha256=db.sha256_bytes((self.dir / "vectors.npy").read_bytes()))
        (self.dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")
        return manifest


def embed_units(cfg: Config, conn, backend_name: str | None = None) -> dict:
    backend = get_backend(cfg, backend_name)
    sid = set_id_for(backend)
    store = VectorStore(cfg, sid)
    rows = conn.execute(
        """SELECT u.id, u.text FROM argument_units u JOIN document_versions v ON v.id=u.version_id
           WHERE v.is_current=1 AND u.method_version=? ORDER BY u.id""", (METHOD_VERSION,)).fetchall()
    todo = [r for r in rows if r["id"] not in store.index]
    run_id = db.new_run_id("embed")
    conn.execute("INSERT INTO runs(id, kind, code_version, adapter, model, config_json, started_at, status) VALUES(?,?,?,?,?,?,?,?)",
                 (run_id, "embed", code_version(), backend.name, f"{backend.model_id}@{backend.revision}",
                  db.dumps(cfg.section("embed")), db.now(), "running"))
    if todo:
        vecs = backend.encode([r["text"] for r in todo], int(cfg.section("embed").get("batch_size", 16)))
        store.add([r["id"] for r in todo], vecs)
    manifest = {"set_id": sid, "backend": backend.name, "model_id": backend.model_id, "model_revision": backend.revision,
                "is_test_vectors": backend.is_test, "segmentation": METHOD_VERSION, "model_files": backend.manifest,
                "pooling": "cls+l2" if not backend.is_test else "hash-bow+l2", "created_at": db.now(), "run_id": run_id}
    if store.vecs is not None:
        manifest = store.save(manifest)
        conn.execute(
            """INSERT OR REPLACE INTO embedding_sets(id, backend, model_id, model_revision, is_test_vectors, dim, n_vectors, dir,
               manifest_json, run_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, backend.name, backend.model_id, str(backend.revision), int(backend.is_test), int(store.vecs.shape[1]),
             len(store.ids), str(store.dir.relative_to(cfg.root)), db.dumps(manifest), run_id, db.now()))
    usage = {"new_vectors": len(todo), "total": len(store.ids), "truncated_inputs": backend.truncated}
    conn.execute("UPDATE runs SET finished_at=?, status='finished', usage_json=? WHERE id=?", (db.now(), db.dumps(usage), run_id))
    conn.commit()
    return {"set_id": sid, "is_test_vectors": backend.is_test, **usage}
