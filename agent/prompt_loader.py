"""Carga prompts versionados desde agent/prompts/vN.toml (mismo patrón de los talleres 1 y 2)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def list_versions() -> list[int]:
    versions = []
    for path in PROMPTS_DIR.glob("v*.toml"):
        match = re.fullmatch(r"v(\d+)", path.stem)
        if match:
            versions.append(int(match.group(1)))
    return sorted(versions)


def latest_version() -> int:
    versions = list_versions()
    if not versions:
        raise FileNotFoundError(f"No hay prompts en {PROMPTS_DIR}")
    return versions[-1]


def load_prompt(version: int | None = None) -> dict:
    version = version or latest_version()
    path = PROMPTS_DIR / f"v{version}.toml"
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    data["_resolved_version"] = version
    return data
