"""Austauschbare Modellschnittstelle. Das Sprachmodell ist ein austauschbarer Bearbeiter; Originaltexte und
Urteilshistorie hängen nicht vom Anbieter ab.

Adapter:
  none           Standard. Kein Modellaufruf; Interpretationen erhalten Status not_run.
  replay         Liest vorbereitete Antworten aus einer JSON-Datei (Tests). is_real_model_run = False.
  anthropic_api  Anthropic Python SDK; nutzt nur tatsächlich eingerichtete Zugangsdaten aus der Umgebung.
  claude_cli     Ruft die lokal installierte Claude-Code-CLI (`claude -p`) auf, wie im Ausgangsprojekt.

Die Adapter anthropic_api und claude_cli sind in diesem Repository ohne echten Lauf implementiert worden
(kein Modellzugang in der Bauumgebung freigegeben). Siehe docs/PILOT_REPORT.md.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class NotConfigured(RuntimeError):
    pass


class CallLimitReached(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    usage: dict = field(default_factory=dict)
    is_real_model_run: bool = True
    stop_reason: str | None = None


def load_prompt(name: str) -> tuple[str, str]:
    """Rückgabe (prompt_text, version). Dateiname <name>.<version>.txt, höchste Version gewinnt."""
    files = sorted(PROMPT_DIR.glob(f"{name}.v*.txt"), key=lambda p: int(re.search(r"\.v(\d+)\.txt$", p.name).group(1)))
    if not files:
        raise FileNotFoundError(name)
    p = files[-1]
    return p.read_text("utf-8"), p.stem


class Adapter:
    name = "abstract"

    def __init__(self, cfg_llm: dict):
        self.cfg = cfg_llm
        self.calls = 0
        self.max_calls = int(cfg_llm.get("max_calls_per_run", 20))

    def complete(self, system: str, user: str) -> LLMResult:
        if self.calls >= self.max_calls:
            raise CallLimitReached(f"Limit von {self.max_calls} Modellaufrufen erreicht; Lauf pausiert.")
        self.calls += 1
        return self._complete(system, user)

    def _complete(self, system: str, user: str) -> LLMResult:
        raise NotImplementedError


class NoneAdapter(Adapter):
    name = "none"

    def _complete(self, system, user):
        raise NotConfigured("Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.")


class ReplayAdapter(Adapter):
    """Liefert hinterlegte Antworten der Reihe nach bzw. per Schlüssel. Für Tests, niemals als echter Lauf."""
    name = "replay"

    def __init__(self, cfg_llm: dict, responses: list[str] | None = None):
        super().__init__(cfg_llm)
        if responses is None:
            path = cfg_llm.get("replay_file")
            responses = json.loads(Path(path).read_text("utf-8")) if path else []
        self.responses = list(responses)

    def _complete(self, system, user):
        if not self.responses:
            raise NotConfigured("Replay-Datei erschöpft")
        return LLMResult(text=self.responses.pop(0), model="replay", is_real_model_run=False)


class AnthropicAPIAdapter(Adapter):
    name = "anthropic_api"

    def __init__(self, cfg_llm: dict):
        super().__init__(cfg_llm)
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise NotConfigured("Paket 'anthropic' fehlt: pip install 'susa-ai[anthropic]'") from e
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=float(cfg_llm.get("timeout_seconds", 300)), max_retries=2)

    def _complete(self, system, user):
        a = self.anthropic
        kwargs = dict(
            model=self.cfg.get("model", "claude-opus-5-5"),
            max_tokens=int(self.cfg.get("max_tokens", 16000)),
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.cfg.get("effort", "high")},
        )
        try:
            if self.cfg.get("server_fallbacks", True):
                with self.client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs) as s:
                    msg = s.get_final_message()
            else:
                with self.client.messages.stream(**kwargs) as s:
                    msg = s.get_final_message()
        except a.AuthenticationError as e:
            raise NotConfigured(f"Anthropic-Zugang nicht gültig: {e}") from e
        except a.RateLimitError as e:
            raise RuntimeError(f"Rate-Limit: {e}") from e
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        u = msg.usage
        usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
        return LLMResult(text=text, model=msg.model, usage=usage, stop_reason=msg.stop_reason)


class ClaudeCLIAdapter(Adapter):
    name = "claude_cli"

    def __init__(self, cfg_llm: dict):
        super().__init__(cfg_llm)
        self.bin = cfg_llm.get("cli", "claude")
        if shutil.which(self.bin) is None:
            raise NotConfigured(f"CLI '{self.bin}' nicht gefunden")

    def _complete(self, system, user):
        cmd = [self.bin, "-p", "--output-format", "json", "--model", self.cfg.get("model", "claude-opus-5-5"),
               "--system-prompt", system, "--tools", ""]
        r = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=int(self.cfg.get("timeout_seconds", 300)))
        if r.returncode != 0:
            raise RuntimeError(f"claude CLI Fehler {r.returncode}: {r.stderr[:500]}")
        d = json.loads(r.stdout)
        models = list((d.get("modelUsage") or {}).keys())
        return LLMResult(text=d.get("result", ""), model=models[0] if models else self.cfg.get("model"),
                         usage={"total_cost_usd_list_price": d.get("total_cost_usd"), "usage": d.get("usage")},
                         stop_reason=d.get("subtype"))


def get_adapter(cfg_llm: dict, name: str | None = None) -> Adapter:
    name = name or cfg_llm.get("adapter", "none")
    return {"none": NoneAdapter, "replay": ReplayAdapter, "anthropic_api": AnthropicAPIAdapter,
            "claude_cli": ClaudeCLIAdapter}[name](cfg_llm)


def extract_json(text: str) -> dict:
    """JSON-Objekt aus einer Modellantwort holen (auch innerhalb ```json-Blöcken)."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1
