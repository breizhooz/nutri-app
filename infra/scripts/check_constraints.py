#!/usr/bin/env python3
"""Vérifie que shared/constraints.txt reste la SOURCE UNIQUE des versions Python.

  python3 infra/scripts/check_constraints.py     # exit 1 au premier écart listé

Règles contrôlées :
  - chaque service-*/requirements.txt (et requirements-nodeps.txt s'il existe)
    commence par `-c ../shared/constraints.txt` ; chaque requirements-dev.txt
    inclut `-r requirements.txt` ;
  - les requirements ne portent AUCUNE version (juste nom + extras), sauf les
    requirements par URL (`nom @ https://...`) ;
  - toute lib demandée (services + dépendances de shared/pyproject.toml) est
    épinglée (`==`) dans constraints.txt.

Aucune dépendance hors stdlib (tourne dans le job CI infra-check).
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
CONSTRAINTS = BACKEND / "shared" / "constraints.txt"
PYPROJECT = BACKEND / "shared" / "pyproject.toml"
SERVICES = ["user", "recipe", "menu", "crawler", "notification", "nutrition", "profile"]

REQ_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(.*)$")


def normalize(name: str) -> str:
    """Nom de paquet normalisé (PEP 503) : PyJWT == pyjwt, foo_bar == foo-bar."""
    return re.sub(r"[-_.]+", "-", name).lower()


def meaningful_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def load_constraints(errors: list[str]) -> set[str]:
    pinned: set[str] = set()
    for line in meaningful_lines(CONSTRAINTS):
        m = REQ_RE.match(line)
        if not m or m.group(2) or not m.group(3).startswith("=="):
            errors.append(f"constraints.txt : « {line} » doit être de la forme nom==version")
            continue
        name = normalize(m.group(1))
        if name in pinned:
            errors.append(f"constraints.txt : {m.group(1)} épinglé deux fois")
        pinned.add(name)
    return pinned


def check_requirements(
    path: Path, header: str, pinned: set[str], errors: list[str]
) -> None:
    rel = path.relative_to(BACKEND)
    if not path.exists():
        errors.append(f"{rel} : fichier absent")
        return
    lines = meaningful_lines(path)
    if header not in lines:
        errors.append(f"{rel} : ligne « {header} » manquante")
    for line in lines:
        if line.startswith("-"):
            continue
        if " @ " in line:  # requirement par URL : la version est dans l'URL
            continue
        m = REQ_RE.match(line)
        if not m:
            errors.append(f"{rel} : ligne illisible « {line} »")
            continue
        if m.group(3):
            errors.append(
                f"{rel} : « {line} » porte une version → la mettre dans constraints.txt"
            )
        if normalize(m.group(1)) not in pinned:
            errors.append(f"{rel} : {m.group(1)} n'est pas épinglé dans constraints.txt")


def check_shared(pinned: set[str], errors: list[str]) -> None:
    deps = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
    for dep in deps:
        name = REQ_RE.match(dep).group(1)
        if normalize(name) not in pinned:
            errors.append(
                f"shared/pyproject.toml : {name} n'est pas épinglé dans constraints.txt"
            )


def main() -> int:
    errors: list[str] = []
    pinned = load_constraints(errors)
    for svc in SERVICES:
        base = BACKEND / f"service-{svc}"
        check_requirements(
            base / "requirements.txt", "-c ../shared/constraints.txt", pinned, errors
        )
        check_requirements(
            base / "requirements-dev.txt", "-r requirements.txt", pinned, errors
        )
        nodeps = base / "requirements-nodeps.txt"  # optionnel (pip --no-deps)
        if nodeps.exists():
            check_requirements(nodeps, "-c ../shared/constraints.txt", pinned, errors)
    check_shared(pinned, errors)

    if errors:
        print("✗ dépendances Python :", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"✓ dépendances Python : {len(pinned)} versions dans constraints.txt, "
          f"{len(SERVICES)} services conformes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
