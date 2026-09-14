"""Connect-a-model page (deferred onboarding, Ben's design 2026-09-13).

Reached from the capture flow the first time a scan needs identifying (or any
time via /setup). Three options as equal cards, with live detection of the
Claude Code CLI and local model servers — most makers get a zero-credential
path on screen. The API key is just one card, not the front door.
"""

from .ui import BASE_CSS

SETUP_PAGE = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parts Pile — Connect a model</title>
<style>{BASE_CSS}
 .wrap{{max-width:640px;margin:40px auto;padding:0 20px}}
 h1{{font-size:20px;margin:0 0 4px}}
 .sub{{font-size:14px;color:var(--dim);margin-bottom:20px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:18px 20px;margin-bottom:14px}}
 .card h2{{font-size:15px;margin:0 0 4px;display:flex;align-items:center;gap:10px}}
 .card p{{font-size:13px;line-height:1.5;color:var(--dim);margin:4px 0 10px}}
 .pill{{font-size:11px;padding:2px 9px;border-radius:12px}}
 .pill.on{{background:#1c5c2e}}.pill.off{{background:#3a4048;color:var(--dim)}}
 .row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
 .row input,.row select{{flex:1;min-width:180px}}
 .msg{{font-size:13px;margin-top:8px;min-height:18px}}
 .msg.ok{{color:var(--green)}}.msg.err{{color:#f28b82}}
</style></head><body>
<div class="wrap">
 <h1>Connect a model</h1>
 <div class="sub">Scans wait in the queue until a vision model is connected —
  pick whichever fits you. You can change this any time at <code>/setup</code>.</div>

 <div class="card" id="card-claude">
  <h2>Use your Claude account <span class="pill off" id="pill-claude">checking…</span></h2>
  <p>Uses the Claude Code CLI you're already logged into — no API key, billed to
     your existing subscription. The most accurate option.</p>
  <div class="row"><button class="b-blue" id="btn-claude" onclick="useClaude()">Use Claude account</button></div>
  <div class="msg" id="msg-claude"></div>
 </div>

 <div class="card" id="card-local">
  <h2>Use a local model
   <span class="pill off" id="pill-ollama">Ollama: checking…</span>
   <span class="pill off" id="pill-lms">LM Studio: checking…</span></h2>
  <p>Free, fully private, runs on your machine. Needs a vision-capable model in
     Ollama or LM Studio (see the README for the recommended recipe).</p>
  <div class="row">
   <select id="local-model"><option value="">no local server detected</option></select>
   <button class="b-green" onclick="useLocal()">Use local model</button>
  </div>
  <div class="msg" id="msg-local"></div>
 </div>

 <div class="card">
  <h2>Anthropic API key</h2>
  <p>Pay-per-scan via the Anthropic API — for machines without Claude Code or a
     local model. Stored only on this machine, owner-readable.</p>
  <form class="row" method="post" action="/api/setup">
   <input type="password" name="api_key" placeholder="sk-ant-…" required>
   <button class="b-gray" type="submit">Save key</button>
  </form>
 </div>
</div>
<script>
let det=null;
async function refresh(){{
  const r=await fetch('/api/setup/status'); det=await r.json();
  const pc=document.getElementById('pill-claude');
  pc.textContent=det.detect.claude_cli?'detected':'not found';
  pc.className='pill '+(det.detect.claude_cli?'on':'off');
  document.getElementById('btn-claude').disabled=!det.detect.claude_cli;
  const po=document.getElementById('pill-ollama');
  po.textContent='Ollama: '+(det.detect.ollama.found?'detected':'not found');
  po.className='pill '+(det.detect.ollama.found?'on':'off');
  const pl=document.getElementById('pill-lms');
  pl.textContent='LM Studio: '+(det.detect.lm_studio.found?'detected':'not found');
  pl.className='pill '+(det.detect.lm_studio.found?'on':'off');
  const sel=document.getElementById('local-model'); sel.innerHTML='';
  const opts=[];
  det.detect.ollama.models.forEach(m=>opts.push({{v:'ollama|'+m,t:m+'  (Ollama)'}}));
  det.detect.lm_studio.models.filter(m=>!m.includes('embed'))
    .forEach(m=>opts.push({{v:'lms|'+m,t:m+'  (LM Studio)'}}));
  if(!opts.length){{sel.innerHTML='<option value="">no local server detected</option>';}}
  opts.forEach(o=>{{const el=document.createElement('option');el.value=o.v;el.textContent=o.t;sel.appendChild(el);}});
}}
async function useClaude(){{
  const m=document.getElementById('msg-claude');
  const r=await fetch('/api/setup/claude-code',{{method:'POST'}});
  if(r.ok){{m.textContent='Connected — your scans will start identifying.';m.className='msg ok';
           setTimeout(()=>location.href='/',900);}}
  else{{m.textContent=(await r.json()).detail||'failed';m.className='msg err';}}
}}
async function useLocal(){{
  const m=document.getElementById('msg-local');
  const v=document.getElementById('local-model').value;
  if(!v){{m.textContent='No local model server detected on ports 11434 / 1234.';m.className='msg err';return;}}
  const [kind,model]=[v.split('|')[0], v.split('|').slice(1).join('|')];
  const body=kind==='ollama'?{{provider:'ollama',model:model}}
    :{{provider:'openai_compat',model:model,base_url:'http://localhost:1234/v1'}};
  const r=await fetch('/api/setup/local',{{method:'POST',
    headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  if(r.ok){{m.textContent='Connected — your scans will start identifying.';m.className='msg ok';
           setTimeout(()=>location.href='/',900);}}
  else{{m.textContent=(await r.json()).detail||'failed';m.className='msg err';}}
}}
refresh();
</script>
</body></html>"""
