"""First-run setup: paste an Anthropic API key (cloud-first onboarding).

Local-model users are the advanced path — they configure via env vars per the
README and never see this page (needs_setup only fires for provider=anthropic
with no key).
"""

from .ui import BASE_CSS

SETUP_PAGE = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parts Pile — Setup</title>
<style>{BASE_CSS}
 .wrap{{max-width:520px;margin:60px auto;padding:0 20px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:26px}}
 h1{{font-size:20px;margin:0 0 6px}}
 p{{font-size:14px;line-height:1.5;color:var(--dim)}}
 form{{display:flex;gap:10px;margin-top:14px}}
 input{{flex:1}}
 .alt{{margin-top:22px;font-size:13px;color:var(--dim)}}
</style></head><body>
<div class="wrap"><div class="card">
 <h1>Welcome to Parts Pile</h1>
 <p>Scans are identified by Claude via the Anthropic API. Paste an API key to get
 started — create one at
 <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com/settings/keys</a>.
 It's stored only on this machine (<code>~/.partspile/config</code>, owner-readable).</p>
 <form method="post" action="/api/setup">
  <input type="password" name="api_key" placeholder="sk-ant-..." required autofocus>
  <button class="b-blue" type="submit">Save &amp; start</button>
 </form>
 <p class="alt">Running a local model instead? Set <code>PARTS_PILE_PROVIDER</code>
 (and friends) per the README — no key needed.</p>
</div></div>
</body></html>"""
