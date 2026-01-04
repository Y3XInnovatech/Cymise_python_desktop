from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure src/ is importable when running as a script
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cymise.graph.service import GraphService  # noqa: E402
from cymise.store.db import create_db, get_engine, get_session  # noqa: E402
from cymise.store.repo import StoreRepository  # noqa: E402
from cymise.ui.app import run_app  # noqa: E402


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the CyMiSE desktop app.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite database (defaults to cymise.db in repo root).",
    )
    args, extra = parser.parse_known_args(argv)

    engine = get_engine(args.db) if args.db else get_engine()
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    graph_service = GraphService(repo)

    try:
        return run_app(graph_service, argv=extra if extra else None)
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
