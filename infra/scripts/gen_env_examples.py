#!/usr/bin/env python3
"""Génère les .env.example depuis les classes Settings pydantic (le code = contrat).

Deux modes :
  python3 infra/scripts/gen_env_examples.py            # (ré)écrit infra/env/examples/<svc>.env.example
  python3 infra/scripts/gen_env_examples.py --check    # vérifie que la chaîne env_file de chaque
                                                       # service couvre tous les champs requis
                                                       # (sans défaut) de sa classe Settings.
                                                       # Exit 1 si un champ requis manque.

Les config.py sont parsés par AST — aucun import des services, donc pas besoin
de leurs venvs ni de leurs dépendances.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SERVICES = ["user", "recipe", "menu", "crawler", "notification", "nutrition", "profile"]
EXAMPLES_DIR = BACKEND / "infra" / "env" / "examples"

# Heuristique « ce nom sent le secret » → orienté vers secrets/<svc>.secrets.env
SECRET_RE = re.compile(r"SECRET|TOKEN|PASSWORD|_KEY$|_KEYS$|API_KEY|CLIENT_ID|USERNAME")


@dataclass
class Field:
    name: str
    type_: str
    default: str | None  # None = requis (pas de défaut)

    @property
    def required(self) -> bool:
        return self.default is None

    @property
    def secret(self) -> bool:
        return bool(SECRET_RE.search(self.name))


def parse_settings(config_py: Path) -> list[Field]:
    """Extrait les champs de la classe Settings (annotations au niveau classe)."""
    tree = ast.parse(config_py.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            fields = []
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                    continue
                name = stmt.target.id
                if name == "model_config":
                    continue
                default = ast.unparse(stmt.value) if stmt.value is not None else None
                fields.append(Field(name, ast.unparse(stmt.annotation), default))
            return fields
    raise SystemExit(f"classe Settings introuvable dans {config_py}")


def env_keys(path: Path) -> set[str]:
    """Clés d'un fichier dotenv (lignes KEY=…, commentaires ignorés)."""
    keys = set()
    if not path.exists():
        return keys
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def compose_env(svc: str) -> set[str]:
    """Variables injectées par compose pour service-<svc> : clés du bloc
    `environment:` + contenu des fichiers de la chaîne `env_file`."""
    import yaml

    keys: set[str] = set()
    for frag in (BACKEND / "infra" / "compose").glob("*.yml"):
        doc = yaml.safe_load(frag.read_text()) or {}
        spec = (doc.get("services") or {}).get(f"service-{svc}")
        if not spec:
            continue
        for entry in spec.get("environment", []) or []:
            if isinstance(entry, str):
                keys.add(entry.split("=", 1)[0])
            else:  # mapping
                keys.update(spec["environment"])
        files = spec.get("env_file", []) or []
        for f in [files] if isinstance(files, str) else files:
            keys |= env_keys((frag.parent / f).resolve())
    return keys


def example_text(svc: str, fields: list[Field]) -> str:
    lines = [
        f"# ── service-{svc} — contrat d'environnement ───────────────────────────────",
        "# GÉNÉRÉ par infra/scripts/gen_env_examples.py depuis app/core/config.py — ne pas éditer.",
        "# Requis = pas de valeur par défaut dans Settings. Les noms marqués [secret]",
        f"# vont dans infra/env/secrets/{svc}.secrets.env, le reste dans services/{svc}.env.",
        "",
    ]
    for f in fields:
        tag = " [secret]" if f.secret else ""
        if f.required:
            lines.append(f"# requis ({f.type_}){tag}")
            lines.append(f"{f.name}=")
        else:
            empty_defaults = ("None", "''", '""')
            value = "" if f.default in empty_defaults else f.default.strip("'\"")
            lines.append(f"# optionnel ({f.type_}, défaut: {f.default}){tag}")
            lines.append(f"#{f.name}={value}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="vérifie la couverture des champs requis")
    args = parser.parse_args()

    failed = False
    for svc in SERVICES:
        config_py = BACKEND / f"service-{svc}" / "app" / "core" / "config.py"
        fields = parse_settings(config_py)

        if args.check:
            provided = compose_env(svc)
            missing = [f.name for f in fields if f.required and f.name not in provided]
            if missing:
                failed = True
                print(f"✗ service-{svc} : requis non fournis par la chaîne env_file/environment : {', '.join(missing)}")
            else:
                print(f"✓ service-{svc} : {sum(f.required for f in fields)} requis couverts ({len(fields)} champs)")
        else:
            EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            out = EXAMPLES_DIR / f"{svc}.env.example"
            out.write_text(example_text(svc, fields))
            print(f"écrit {out.relative_to(BACKEND)} ({len(fields)} champs)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
