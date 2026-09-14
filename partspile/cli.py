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
    serve.add_argument("--port", type=int, default=None,
                       help="port to serve on (default: 8000, or next free)")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--no-open", action="store_true",
                       help="don't open the browser on start")
    serve.add_argument("--data-dir", help="override ~/.partspile")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:] or ["serve"])

    if getattr(args, "data_dir", None):
        os.environ["PARTS_PILE_DATA_DIR"] = args.data_dir

    port = getattr(args, "port", None)
    host = getattr(args, "host", "0.0.0.0")
    if port is None:
        port = _free_port(host, 8000)
        if port != 8000:
            print(f"Port 8000 is in use — serving on {port} instead.")
    elif not _port_free(host, port):
        print(f"Port {port} is already in use. Try another --port, or omit "
              "--port to auto-pick a free one.")
        return 1
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
    uvicorn.run(app, host=host, port=port)
    return 0


def _port_free(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host if host != "0.0.0.0" else "", port))
            return True
        except OSError:
            return False


def _free_port(host: str, start: int) -> int:
    for p in range(start, start + 20):
        if _port_free(host, p):
            return p
    return start  # let uvicorn report the bind error


if __name__ == "__main__":
    raise SystemExit(main())
