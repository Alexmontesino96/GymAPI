#!/usr/bin/env python3
"""
Run Alembic migrations programmatically with optional auto-merge for multiple heads.

Usage examples:
  python scripts/db_migrate.py                # upgrade to head
  python scripts/db_migrate.py --merge-heads  # auto-merge multiple heads, then upgrade
  python scripts/db_migrate.py --revision <rev>
"""
import argparse
import sys
import os
from typing import List

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory


def get_config(alembic_ini_path: str) -> Config:
    cfg = Config(alembic_ini_path)
    # Ensure paths are relative to repo root
    cfg.set_main_option("script_location", "migrations")
    return cfg


def list_heads(cfg: Config) -> List[str]:
    script = ScriptDirectory.from_config(cfg)
    return script.get_heads()


def ensure_merged_heads(cfg: Config, message: str = "merge heads") -> None:
    heads = list_heads(cfg)
    if len(heads) <= 1:
        print(f"Alembic: single head detected ({heads[0] if heads else 'none'}). No merge needed.")
        return
    print(f"Alembic: multiple heads detected: {heads}. Creating merge revision...")
    command.merge(cfg, heads=heads, message=message)
    print("Alembic: merge revision created.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alembic migrations")
    parser.add_argument("--alembic-ini", default="alembic.ini", help="Path to alembic.ini")
    parser.add_argument("--revision", default="head", help="Target revision (default: head)")
    parser.add_argument("--merge-heads", action="store_true", help="Auto-merge multiple heads before upgrading")
    args = parser.parse_args()

    ini_path = os.path.abspath(args.alembic_ini)
    if not os.path.exists(ini_path):
        print(f"Error: alembic ini not found at {ini_path}", file=sys.stderr)
        return 2

    cfg = get_config(ini_path)

    try:
        if args.merge_heads:
            ensure_merged_heads(cfg)
        print(f"Alembic: upgrading to {args.revision}...")
        command.upgrade(cfg, args.revision)
        print("Alembic: upgrade completed successfully.")
        return 0
    except Exception as e:
        print(f"Alembic migration failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

