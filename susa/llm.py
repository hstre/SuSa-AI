"""Austauschbare Modellschnittstelle mit gemeinsamem, persistent protokolliertem Aufrufbudget.

Budget
  Ein Budget (Tabelle model_budgets) wird ausdrücklich angelegt (`susa budget create`). Jeder Aufrufversuch –
  auch Fehlversuche und Wiederholungen – wird VOR dem Aufruf in model_calls eingetragen und zählt gegen das Budget.
  Der Zähler liegt in der Datenbank, nicht im Adapterobjekt: neue Adapterinstanzen, Oberflächenaufrufe oder ein
  Neustart des Prozesses können das Limit nicht zurücksetzen. Ist das Budget erschöpft, wird der Versuch als
  'refused_budget' protokolliert und CallLimitReached ausgelöst; es wird kein neues Budget angelegt.

Adapter
  none           Kein Modellaufruf; Interpretationen erhalten Status not_run.
  replay         Vorbereitete Antworten (Funktionstests). Nie als echter Modelllauf markiert.
  anthropic_api  Anthropic Python SDK. Interne SDK-Wiederholungen sind abgeschaltet; Wiederholungen laufen über
                 das Budget.
  claude_cli     Lokal angemeldete Claude-Code-CLI (`claude -p`), ohne Werkzeuge, mit eigenem Systemprompt,
                 in einem leeren Arbeitsverzeichnis.

Echte Dienste (anthropic_api, claude_cli) laufen nur mit Budget.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import db

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
REAL_ADAPTERS = ("anthropic_api", "claude_cli")


class NotConfigured(RuntimeError):
    pass


class CallLimitReached(RuntimeError):
    pass


class TransientError(RuntimeError):
    """Fehler, bei dem eine Wiederholung sinnvoll sein kann (Zeitüberschreitung, Rate-Limit, 5xx)."""


@dataclass
class LLMResult:
    text: str
    model: str
    usage: dict = field(default_factory=dict)
    is_real_model_run: bool = True
    stop_reason: str | None = None
    call_id: int | None = None
    attempts: int = 1


def load_prompt(name: str) -> tuple[str, str]:
    """Rückgabe (prompt_text, version). Dateiname <name>.<version>.txt, höchste Version gewinnt."""
    files = sorted(PROMPT_DIR.glob(f"{name}.v*.txt"), key=lambda p: int(re.search(r"\.v(\d+)\.txt$", p.name).group(1)))
    if not files:
        raise FileNotFoundError(name)
    p = files[-1]
    return p.read_text("utf-8"), p.stem


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


# ------------------------------------------------------------------ Budget

def create_budget(conn, label: str, max_calls: int, adapter: str | None = None, model: str | None = None, notes: str = "") -> str:
    bid = f"budget-{db.now()[:10]}-{uuid.uuid4().hex[:8]}"
    conn.execute("INSERT INTO model_budgets(id, label, max_calls, adapter, model, created_at, notes) VALUES(?,?,?,?,?,?,?)",
                 (bid, label, int(max_calls), adapter, model, db.now(), notes))
    conn.commit()
    return bid


def budget_status(conn, budget_id: str) -> dict:
    b = conn.execute("SELECT * FROM model_budgets WHERE id=?", (budget_id,)).fetchone()
    if b is None:
        raise NotConfigured(f"Budget {budget_id} existiert nicht")
    rows = conn.execute("SELECT outcome, COUNT(*) n FROM model_calls WHERE budget_id=? GROUP BY outcome", (budget_id,)).fetchall()
    by = {r["outcome"]: r["n"] for r in rows}
    used = sum(n for o, n in by.items() if o != "refused_budget")
    return {"id": b["id"], "label": b["label"], "max_calls": b["max_calls"], "used": used,
            "remaining": max(0, b["max_calls"] - used), "by_outcome": by, "closed_at": b["closed_at"]}


class Budget:
    def __init__(self, conn, budget_id: str):
        self.conn, self.id = conn, budget_id
        st = budget_status(conn, budget_id)
        if st["closed_at"]:
            raise NotConfigured(f"Budget {budget_id} ist geschlossen")

    def reserve(self, *, adapter: str, model: str | None, is_real: bool, purpose: str, run_id: str | None, attempt: int,
                est_input_tokens: int | None, max_output_tokens: int | None) -> int:
        """Atomar prüfen und eintragen (BEGIN IMMEDIATE sperrt auch gegenüber anderen Prozessen)."""
        c = self.conn
        c.commit()
        c.execute("BEGIN IMMEDIATE")
        try:
            b = c.execute("SELECT max_calls, closed_at FROM model_budgets WHERE id=?", (self.id,)).fetchone()
            used = c.execute("SELECT COUNT(*) FROM model_calls WHERE budget_id=? AND outcome!='refused_budget'", (self.id,)).fetchone()[0]
            ok = b["closed_at"] is None and used < b["max_calls"]
            cur = c.execute(
                """INSERT INTO model_calls(budget_id, run_id, attempt, adapter, model_requested, is_real_service, purpose, est_input_tokens,
                   max_output_tokens, started_at, finished_at, outcome, error) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.id, run_id, attempt, adapter, model, int(is_real), purpose, est_input_tokens, max_output_tokens, db.now(),
                 None if ok else db.now(), "started" if ok else "refused_budget",
                 None if ok else f"Budget erschöpft ({used}/{b['max_calls']})"))
            c.commit()
        except Exception:
            c.rollback()
            raise
        if not ok:
            raise CallLimitReached(f"Budget {self.id} erschöpft ({used}/{b['max_calls']} Aufrufe); Lauf gestoppt.")
        return cur.lastrowid

    def finish(self, call_id: int, outcome: str, *, model_reported: str | None = None, usage: dict | None = None,
               error: str | None = None, raw_path: str | None = None) -> None:
        self.conn.execute("UPDATE model_calls SET finished_at=?, outcome=?, model_reported=?, usage_json=?, error=?, raw_path=? WHERE id=?",
                          (db.now(), outcome, model_reported, db.dumps(usage) if usage else None, error, raw_path, call_id))
        self.conn.commit()


# ------------------------------------------------------------------ Adapter

class Adapter:
    name = "abstract"
    is_real = False

    def __init__(self, cfg_llm: dict, conn=None, budget_id: str | None = None):
        self.cfg = cfg_llm
        self.conn = conn
        budget_id = budget_id or cfg_llm.get("budget_id")
        self.budget = Budget(conn, budget_id) if (conn is not None and budget_id) else None
        if self.is_real and self.budget is None:
            raise NotConfigured(f"Adapter {self.name} braucht ein ausdrücklich angelegtes Budget (susa budget create) und --budget.")
        self.max_retries = int(cfg_llm.get("max_retries", 1))
        self.max_output_tokens = int(cfg_llm.get("max_tokens", 4000))

    @property
    def model(self) -> str | None:
        return self.cfg.get("model") if self.is_real else self.name

    def complete(self, system: str, user: str, *, purpose: str = "", run_id: str | None = None,
                 raw_dir: Path | None = None) -> LLMResult:
        attempt = 0
        while True:
            attempt += 1
            call_id = None
            self.preflight()  # vor der Reservierung: eine Verweigerung zählt nicht als Aufruf
            if self.budget is not None:
                call_id = self.budget.reserve(adapter=self.name, model=self.model, is_real=self.is_real, purpose=purpose, run_id=run_id,
                                              attempt=attempt, est_input_tokens=estimate_tokens(system + user),
                                              max_output_tokens=self.max_output_tokens)
            try:
                res = self._complete(system, user)
            except NotConfigured:
                if self.budget is not None and call_id is not None:
                    self.budget.finish(call_id, "error", error="nicht konfiguriert")
                raise
            except TransientError as e:
                if self.budget is not None:
                    self.budget.finish(call_id, "error", error=f"transient: {e}"[:2000])
                if attempt <= self.max_retries:
                    continue
                raise RuntimeError(f"{e} (nach {attempt} Versuchen)") from e
            except Exception as e:
                if self.budget is not None:
                    self.budget.finish(call_id, "error", error=repr(e)[:2000])
                raise
            raw_path = None
            if raw_dir is not None:
                raw_dir.mkdir(parents=True, exist_ok=True)
                rp = raw_dir / f"call-{call_id or uuid.uuid4().hex[:8]}.json"
                rp.write_text(json.dumps({"text": res.text, "model": res.model, "usage": res.usage, "stop_reason": res.stop_reason},
                                         ensure_ascii=False, indent=1), "utf-8")
                raw_path = str(rp)
            if self.budget is not None:
                self.budget.finish(call_id, "success", model_reported=res.model, usage=res.usage, raw_path=raw_path)
            res.call_id, res.attempts = call_id, attempt
            return res

    def preflight(self) -> None:
        """Bedingungen, die vor jedem Aufruf erfüllt sein müssen (z. B. reine Abo-Nutzung). Standard: keine."""

    def _complete(self, system: str, user: str) -> LLMResult:
        raise NotImplementedError


class NoneAdapter(Adapter):
    name = "none"

    def complete(self, system, user, **kw):
        raise NotConfigured("Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.")


class ReplayAdapter(Adapter):
    """Liefert hinterlegte Antworten der Reihe nach. Für Funktionstests, niemals als echter Lauf.
    Einträge, die mit 'TRANSIENT' beginnen, simulieren einen wiederholbaren Fehler."""
    name = "replay"

    def __init__(self, cfg_llm: dict, responses: list[str] | None = None, conn=None, budget_id: str | None = None):
        super().__init__(cfg_llm, conn, budget_id)
        if responses is None:
            path = cfg_llm.get("replay_file")
            responses = json.loads(Path(path).read_text("utf-8")) if path else []
        self.responses = list(responses)

    def _complete(self, system, user):
        if not self.responses:
            raise NotConfigured("Replay-Antworten erschöpft")
        r = self.responses.pop(0)
        if r.startswith("TRANSIENT"):
            raise TransientError(r)
        return LLMResult(text=r, model="replay", is_real_model_run=False)


class AnthropicAPIAdapter(Adapter):
    name = "anthropic_api"
    is_real = True

    def __init__(self, cfg_llm: dict, conn=None, budget_id: str | None = None):
        super().__init__(cfg_llm, conn, budget_id)
        try:
            import anthropic
        except ImportError as e:
            raise NotConfigured("Paket 'anthropic' fehlt: pip install 'susa-ai[anthropic]'") from e
        self.anthropic = anthropic
        # max_retries=0: jede Wiederholung soll sichtbar über das Budget laufen
        self.client = anthropic.Anthropic(timeout=float(cfg_llm.get("timeout_seconds", 300)), max_retries=0)

    def _complete(self, system, user):
        a = self.anthropic
        kwargs = dict(model=self.cfg.get("model", "claude-opus-5-5"), max_tokens=self.max_output_tokens, system=system,
                      messages=[{"role": "user", "content": user}], output_config={"effort": self.cfg.get("effort", "medium")})
        try:
            with self.client.messages.stream(**kwargs) as s:
                msg = s.get_final_message()
        except a.AuthenticationError as e:
            raise NotConfigured(f"Anthropic-Zugang nicht gültig: {e}") from e
        except (a.RateLimitError, a.APIConnectionError, a.APITimeoutError, a.InternalServerError) as e:
            raise TransientError(repr(e)) from e
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return LLMResult(text=text, model=msg.model, usage=usage, stop_reason=msg.stop_reason)


class ClaudeCLIAdapter(Adapter):
    name = "claude_cli"
    is_real = True

    def __init__(self, cfg_llm: dict, conn=None, budget_id: str | None = None):
        super().__init__(cfg_llm, conn, budget_id)
        self.bin = cfg_llm.get("cli", "claude")
        if shutil.which(self.bin) is None:
            raise NotConfigured(f"CLI '{self.bin}' nicht gefunden")

    def preflight(self) -> None:
        """Nur reine Abo-Nutzung (llm.subscription_only, Standard an). Vor dem Aufruf: OAuth-Anmeldung, kein
        API-Schlüssel, Zusatznutzung laut CLI-Zustand abgeschaltet; dazu darf kein früherer Aufruf dieses Budgets
        eine nutzbare oder genutzte Zusatznutzung oder fehlende Rate-Limit-Angaben gezeigt haben."""
        if not self.cfg.get("subscription_only", True):
            return
        problems = check_subscription_only(self.bin, self.conn, self.budget.id if self.budget else None)
        if problems:
            raise NotConfigured("Abrechnung nicht als reine Abo-Nutzung bestätigt, kein Aufruf: " + "; ".join(problems))

    def command(self, system: str) -> list[str]:
        return [self.bin, "-p", "--output-format", "stream-json", "--verbose", "--model", self.cfg.get("model", "claude-opus-5-5"),
                "--effort", self.cfg.get("effort", "medium"), "--system-prompt", system, "--tools", "",
                "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]

    def _complete(self, system, user):
        env = dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(self.max_output_tokens))
        with tempfile.TemporaryDirectory(prefix="susa-cli-") as cwd:  # leeres Verzeichnis: kein Projektkontext
            try:
                r = subprocess.run(self.command(system), input=user, capture_output=True, text=True, cwd=cwd, env=env,
                                   timeout=int(self.cfg.get("timeout_seconds", 300)))
            except subprocess.TimeoutExpired as e:
                raise TransientError(f"Zeitüberschreitung nach {e.timeout} s") from e
        d, rate_limit = None, None
        for line in r.stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                d = ev
            elif ev.get("type") == "rate_limit_event":
                rate_limit = ev.get("rate_limit_info")
        if d is None:
            raise RuntimeError(f"CLI-Ausgabe ohne Ergebnis (rc={r.returncode}): {r.stdout[-300:]} {r.stderr[:500]}")
        if r.returncode != 0 or d.get("is_error"):
            msg = f"CLI-Fehler rc={r.returncode} subtype={d.get('subtype')}: {str(d.get('result'))[:500]} {r.stderr[:300]}"
            if any(k in msg.lower() for k in ("rate", "overloaded", "timeout", "529", "503")):
                raise TransientError(msg)
            raise RuntimeError(msg)
        mu = d.get("modelUsage") or {}
        main = max(mu, key=lambda k: (mu[k] or {}).get("outputTokens", 0)) if mu else None
        usage = {"usage": d.get("usage"), "modelUsage": mu, "total_cost_usd_list_price": d.get("total_cost_usd"),
                 "duration_ms": d.get("duration_ms"), "num_turns": d.get("num_turns"), "rate_limit_info": rate_limit}
        # Erreicht die Ausgabe die Grenze, setzt die CLI in einem weiteren Zug fort und liefert in "result" nur dessen
        # Text. Die Antwort ist dann unvollständig und wird so markiert (nicht stillschweigend weiterverarbeitet).
        stop = "output_split" if (d.get("num_turns") or 1) > 1 else d.get("subtype")
        return LLMResult(text=d.get("result") or "", model=main or "unbekannt", usage=usage, stop_reason=stop)


OVERAGE_ACTIVE = ("allowed", "allowed_warning")


def check_subscription_only(cli_bin: str, conn=None, budget_id: str | None = None) -> list[str]:
    """Belege für reine Abo-Nutzung ohne kostenpflichtige Zusatznutzung. Leere Liste = bestätigt."""
    problems = []
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        if os.environ.get(k):
            problems.append(f"{k} gesetzt (API-Abrechnung möglich)")
    try:
        st = json.loads(subprocess.run([cli_bin, "auth", "status"], capture_output=True, text=True, timeout=60).stdout)
        if not (st.get("loggedIn") and st.get("authMethod") == "oauth_token" and st.get("apiProvider") == "firstParty"):
            problems.append(f"Anmeldung nicht OAuth/firstParty: {st.get('authMethod')}/{st.get('apiProvider')}")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        problems.append(f"Anmeldestatus nicht lesbar: {e}")
    try:
        state = json.loads((Path.home() / ".claude.json").read_text("utf-8"))
        if not state.get("cachedExtraUsageDisabledReason"):
            problems.append("Zusatznutzung laut CLI-Zustand nicht als abgeschaltet vermerkt")
    except (OSError, ValueError):
        problems.append("CLI-Zustand (~/.claude.json) nicht lesbar")
    if conn is not None:
        problems += quota_problems(conn)
    if conn is not None and budget_id:
        for row in conn.execute("SELECT id, usage_json FROM model_calls WHERE budget_id=? AND outcome='success' AND adapter='claude_cli'",
                                (budget_id,)):
            rl = (json.loads(row[1] or "{}") or {}).get("rate_limit_info")
            if not rl:
                problems.append(f"Aufruf {row[0]} ohne Rate-Limit-Angaben, Abrechnung unklar")
            elif rl.get("isUsingOverage") or rl.get("overageInUse") or rl.get("overageStatus") in OVERAGE_ACTIVE:
                problems.append(f"Aufruf {row[0]} meldet Zusatznutzung (overageStatus={rl.get('overageStatus')}, "
                                f"isUsingOverage={rl.get('isUsingOverage')})")
    return problems


def quota_problems(conn, threshold: float = 0.95, now: float | None = None) -> list[str]:
    """Abo-Kontingent laut den Rate-Limit-Angaben der letzten Antwort. Ist ein noch nicht zurückgesetztes Fenster
    nicht mehr „allowed“ oder fast ausgeschöpft, wird vor dem nächsten Aufruf pausiert (kein verlorener Versuch)."""
    import time
    now = time.time() if now is None else now
    row = conn.execute("SELECT id, usage_json FROM model_calls WHERE adapter='claude_cli' AND usage_json LIKE '%rate_limit_info%' "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return []
    rl = (json.loads(row[1] or "{}") or {}).get("rate_limit_info") or {}
    windows = dict(rl.get("unifiedWindows") or {})
    windows.setdefault("gesamt", {"status": rl.get("status"), "resetsAt": rl.get("resetsAt"), "utilization": None})
    out = []
    for name, w in windows.items():
        if (w.get("resetsAt") or 0) <= now:
            continue
        if w.get("status") not in (None, "allowed") or (w.get("utilization") or 0) >= threshold:
            out.append(f"Kontingent {name} laut Aufruf {row[0]}: status={w.get('status')}, Auslastung={w.get('utilization')}, "
                       f"zurückgesetzt ab {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(w['resetsAt']))}")
    return out


ADAPTERS = {"none": NoneAdapter, "replay": ReplayAdapter, "anthropic_api": AnthropicAPIAdapter, "claude_cli": ClaudeCLIAdapter}


def get_adapter(cfg_llm: dict, name: str | None = None, conn=None, budget_id: str | None = None) -> Adapter:
    name = name or cfg_llm.get("adapter", "none")
    return ADAPTERS[name](cfg_llm, conn=conn, budget_id=budget_id)


def extract_json(text: str) -> dict:
    """JSON-Objekt aus einer Modellantwort holen (auch innerhalb ```json-Blöcken). ValueError, wenn keines da ist."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        raw = m.group(1)
    else:
        i, j = text.find("{"), text.rfind("}")
        if i < 0 or j <= i:
            raise ValueError("keine JSON-Struktur in der Antwort")
        raw = text[i:j + 1]
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("JSON ist kein Objekt")
    return obj
