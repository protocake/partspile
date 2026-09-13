#!/usr/bin/env python3
"""Phone-to-repo photo inbox — interim capture path until the M4 PWA exists.

Run on the Mac:
    python3 tools/photo_inbox.py --dir fixtures_staging/truth_reference

Then open the printed http://<lan-ip>:8100 on the phone (same Wi-Fi).
Tap "Take photo" -> camera -> snap; the shot AUTO-UPLOADS in the background and
the button is ready for the next one (one tap per photo). "Choose from library"
multi-selects existing photos, also auto-uploaded. Files land in --dir named
<prefix->YYYYmmdd-HHMMSS-<n>.jpg. Stdlib only; replaced by the real UI at M4.
"""

import argparse
import datetime
import email.parser
import email.policy
import html
import json
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = """<!doctype html>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parts Pile photo inbox</title>
<style>
 body{font-family:-apple-system,system-ui,sans-serif;margin:1.5rem auto;max-width:30rem;padding:0 1rem}
 .btn{display:block;width:100%;font-size:1.4rem;padding:1rem;margin:.5rem 0;border-radius:.8rem;
      border:none;background:#0a74da;color:#fff}
 .btn.alt{background:#555;font-size:1.1rem;padding:.7rem}
 input[type=text]{font-size:1.1rem;width:100%;padding:.5rem;box-sizing:border-box}
 #log li{margin:.15rem 0} .ok{color:#0a0} .err{color:#c00} .busy{color:#a70}
 code{background:#eee;padding:0 .3rem}
</style>
<h2>Parts Pile photo inbox</h2>
<p>Saving to <code>__DEST__</code> &middot; <span id="count">__COUNT__</span> file(s)</p>
<input type="text" id="prefix" placeholder="optional prefix, e.g. closeup_dip14">
<button class="btn" id="shoot">&#128247; Take photo</button>
<button class="btn alt" id="pick">Choose from library</button>
<input type="file" id="cam" accept="image/*" capture="environment" hidden>
<input type="file" id="lib" accept="image/*" multiple hidden>
<ul id="log"></ul>
<script>
const cam=document.getElementById('cam'), lib=document.getElementById('lib'),
      log=document.getElementById('log'), count=document.getElementById('count');
document.getElementById('shoot').onclick=()=>cam.click();
document.getElementById('pick').onclick=()=>lib.click();
cam.onchange=()=>{upload(cam.files);cam.value='';};
lib.onchange=()=>{upload(lib.files);lib.value='';};
async function upload(files){
  if(!files.length)return;
  const li=document.createElement('li');
  li.textContent='Uploading '+files.length+' photo(s)…'; li.className='busy';
  log.prepend(li);
  const fd=new FormData();
  for(const f of files)fd.append('photos',f,f.name||'photo.jpg');
  fd.append('prefix',document.getElementById('prefix').value);
  try{
    const r=await fetch('/upload',{method:'POST',body:fd});
    const j=await r.json();
    li.className='ok';
    li.textContent='✓ '+j.saved.join(', ');
    count.textContent=j.total;
  }catch(e){li.className='err';li.textContent='✗ upload failed — '+e;}
}
</script>
"""


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def make_handler(dest: Path):
    class Handler(BaseHTTPRequestHandler):
        def _count(self):
            return len([p for p in dest.iterdir() if p.is_file()]) if dest.exists() else 0

        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            body = (PAGE.replace("__DEST__", html.escape(str(dest)))
                        .replace("__COUNT__", str(self._count()))).encode()
            self._send(body, "text/html; charset=utf-8")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
            prefix, files = "", []
            for part in parsed.iter_parts():
                if part.get_param("name", header="content-disposition") == "prefix":
                    prefix = part.get_content().strip()
                elif part.get_filename():
                    files.append(part)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "", prefix)
            dest.mkdir(parents=True, exist_ok=True)
            saved = []
            for i, part in enumerate(files, 1):
                ext = Path(part.get_filename()).suffix.lower() or ".jpg"
                name = f"{safe_prefix + '-' if safe_prefix else ''}{stamp}-{i}{ext}"
                payload = part.get_payload(decode=True)
                if payload:
                    (dest / name).write_bytes(payload)
                    saved.append(name)
            if self.path == "/upload":
                body = json.dumps({"saved": saved, "total": self._count()}).encode()
                self._send(body, "application/json")
            else:
                # POST from a stale/no-JS form: save (done above) and bounce back to the page
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()

        def log_message(self, fmt, *args):  # quieter console
            print(f"  {self.client_address[0]} {args[0] if args else ''}")

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=Path("Photos/inbox"),
                    help="destination directory (default: Photos/inbox)")
    ap.add_argument("--port", type=int, default=8100)
    args = ap.parse_args()
    if "fixtures/" in str(args.dir).replace("\\", "/"):
        raise SystemExit("Refusing to write into fixtures/ (KICKOFF rule) — stage elsewhere.")
    dest = args.dir.resolve()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(dest))
    print(f"Photo inbox → {dest}")
    print(f"On the phone (same Wi-Fi): http://{lan_ip()}:{args.port}")
    print("Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
