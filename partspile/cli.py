"""`partspile` console entry point. Bare invocation serves and opens the browser."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="partspile",
        description="Parts Pile: photo-based electronics part scanner and inventory")
    sub = ap.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="run the web app (default)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--no-open", action="store_true",
                       help="don't open the browser on start")
    serve.add_argument("--data-dir", help="override ~/.partspile")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:] or ["serve"])

    if getattr(args, "data_dir", None):
        os.environ["PARTS_PILE_DATA_DIR"] = args.data_dir
    port = getattr(args, "port", 8000)
    os.environ["PARTS_PILE_PORT"] = str(port)  # QR + /api/lan-url read this

    # Cloud-first nudge, CLI-only: a genuinely fresh install (no config file, no
    # provider/key exported) gets provider=anthropic and the /setup page. Dev
    # checkouts run uvicorn directly and keep the claude_code default untouched.
    from .paths import config_file
    if (not config_file().exists()
            and "PARTS_PILE_PROVIDER" not in os.environ
            and "ANTHROPIC_API_KEY" not in os.environ):
        os.environ["PARTS_PILE_PROVIDER"] = "anthropic"

    import uvicorn

    from .web.app import app
    if not getattr(args, "no_open", False) and sys.stdin.isatty():
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host=getattr(args, "host", "0.0.0.0"), port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
