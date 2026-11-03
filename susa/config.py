"""Konfiguration: Defaults aus config.example.toml, überschrieben durch config.toml (falls vorhanden)."""
from __future__ import annotations

import copy
import os
import subprocess
import tomllib
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from . import __version__

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def code_version() -> str:
    """Paketversion plus Git-Commit (falls verfügbar), damit Läufe reproduzierbar zugeordnet werden können."""
    try:
        sha = subprocess.run(
            ["git", "-C", str(PACKAGE_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(PACKAGE_ROOT), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if sha:
            return f"{__version__}+{sha}{'.dirty' if dirty else ''}"
    except Exception:
        pass
    return __version__


@dataclass
class Config:
    root: Path
    data: dict

    @classmethod
    def load(cls, root: str | Path | None = None) -> "Config":
        root = Path(root or os.environ.get("SUSA_HOME") or Path.cwd()).resolve()
        example = PACKAGE_ROOT / "config.example.toml"
        data = tomllib.loads(example.read_text("utf-8")) if example.exists() else {}
        local = root / "config.toml"
        if local.exists():
            data = _merge(data, tomllib.loads(local.read_text("utf-8")))
        return cls(root=root, data=data)

    def section(self, name: str) -> dict:
        return self.data.get(name, {})

    @cached_property
    def data_dir(self) -> Path:
        p = self.root / self.section("paths").get("data_dir", "data")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @cached_property
    def models_dir(self) -> Path:
        p = self.root / self.section("paths").get("models_dir", "models")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_dir / "susa.sqlite"

    def subdir(self, name: str) -> Path:
        p = self.data_dir / name
        p.mkdir(parents=True, exist_ok=True)
        return p
