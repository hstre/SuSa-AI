"""Fortsetzbarer Durchlauf über Paare einer eingefrorenen Prüfauswahl: Extraktion (Budget-Review, ein Lauf, ohne
Relationsstufe) und Argumentstufe. Abgeschlossene, gültige Stufen werden nie erneut aufgerufen; ein Abbruch
(Budget, Kontingent, unklare Abrechnung) speichert den Stand, die Fortsetzung beginnt beim nächsten offenen Schritt.
Keine Wiederholung fehlgeschlagener Stufen, es sei denn ausdrücklich verlangt (retry_failed)."""
from __future__ import annotations

import json
from pathlib import Path

from . import argument_stage, br_bridge, db, review_set
from .llm import CallLimitReached, NotConfigured


def extraction_ok(pair_dir: Path, passages: dict | None = None) -> bool:
    run = pair_dir / "run-1.json"
    if not run.exists():
        return False
    r = json.loads(run.read_text("utf-8"))
    if not (r["A"].get("dossier") and r["B"].get("dossier")):
        return False
    if passages is not None and (pair_dir / "passages.json").exists():
        stored = json.loads((pair_dir / "passages.json").read_text("utf-8"))
        return all(stored[k]["document_sha256"] == passages[k]["document_sha256"] for k in ("A", "B"))
    return True


def stage_runs(pair_dir: Path) -> list[dict]:
    out = []
    for m in sorted(pair_dir.glob("argument-*/meta.json")):
        meta = json.loads(m.read_text("utf-8"))
        meta["dir"] = str(m.parent)
        out.append(meta)
    return out


def run(cfg, conn, adapter, set_id: str, positions: list[int], docs_root: Path, retry_failed: bool = False) -> dict:
    state_path = cfg.subdir("semantic") / f"{set_id}-batch.json"
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {"set_id": set_id, "pairs": {}}
    items = {int(i["position"]): i for i in review_set.set_items(conn, set_id)}
    stopped = None
    for pos in positions:
        it = items[pos]
        pair_dir = cfg.subdir(f"semantic/{set_id}-p{pos}")
        ps = state["pairs"].setdefault(str(pos), {"comparison_id": it["comparison_id"]})
        try:
            current = {"A": br_bridge.passage(cfg, conn, it["left_unit_id"]), "B": br_bridge.passage(cfg, conn, it["right_unit_id"])}
            if not extraction_ok(pair_dir, current):
                if ps.get("extraction") == "failed" and not retry_failed:
                    ps["note"] = "Extraktion fehlgeschlagen, nicht wiederholt"
                    continue
                br_bridge.run_pair(cfg, conn, adapter, it["left_unit_id"], it["right_unit_id"], 1, pair_dir, relations=False)
                ok = extraction_ok(pair_dir, current)
                ps["extraction"] = "ok" if ok else "failed"
                rep = br_bridge.evaluate(pair_dir)
                (pair_dir / "evaluation.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), "utf-8")
                if not ok:
                    continue
            else:
                ps.setdefault("extraction", "ok (vorhanden)")
            runs = stage_runs(pair_dir)
            valid = [m for m in runs if m.get("status") == "valid"]
            if not valid:
                if runs and not retry_failed:
                    ps["stage"] = f"{runs[-1].get('status')} (nicht wiederholt)"
                    continue
                meta = argument_stage.run(cfg, conn, adapter, pair_dir, label="batch")
                if meta.get("status") in ("not_run",):
                    raise NotConfigured(meta.get("error") or "nicht ausgeführt")
                runs = stage_runs(pair_dir)
                valid = [m for m in runs if m.get("status") == "valid"]
            last = valid[-1] if valid else runs[-1]
            ps.update({"stage": last.get("status"), "stage_run": last["run_id"]})
            argument_stage.write_reports(Path(last["dir"]), docs_root / f"pair{pos}" / "ARGUMENT_STAGE_RAW.md",
                                         docs_root / f"pair{pos}" / "KURZBERICHT.md")
        except (NotConfigured, CallLimitReached) as e:
            stopped = f"Paar {pos}: {e}"
            ps["paused"] = str(e)
            break
        finally:
            ps["updated_at"] = db.now()
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
        ps.pop("paused", None)
    state["stopped"] = stopped
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
    return state
