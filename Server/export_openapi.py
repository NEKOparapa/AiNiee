"""Generate REST and WebSocket contracts without starting the application."""

import argparse
import json
from pathlib import Path

from Server.app import create_app


def export_openapi(path: Path) -> None:
    schema = create_app(token="schema-export").openapi()
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "openapi.json")
    export_openapi(parser.parse_args().output)


if __name__ == "__main__":
    main()
