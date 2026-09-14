"""Inline HTML pages — no build step, no CDNs, vanilla JS only."""

from .ui import nav

MANIFEST = {
    "name": "Parts Pile",
    "short_name": "PartsPile",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#111418",
    "theme_color": "#0a74da",
    "icons": [],
}

CAPTURE_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<title>Parts Pile — capture</title>
<style>
 :root{--blue:#0a74da;--bg:#111418;--card:#1c2128;--txt:#e8eaed;--dim:#9aa0a6}
 body{font-family:-apple-system,system-ui,sans-serif;margin:0 auto;max-width:30rem;
      padding:1rem;background:var(--bg);color:var(--txt)}
 h2{margin:.3rem 0 1rem}
 .btn{display:block;width:100%;font-size:1.3rem;padding:1rem;margin:.5rem 0;
      border-radius:.8rem;border:none;background:var(--blue);color:#fff}
 .btn.alt{background:#3a4048;font-size:1.05rem;padding:.7rem}
 .btn:disabled{opacity:.5}
 input[type=text]{font-size:1.05rem;width:100%;padding:.6rem;margin:.25rem 0;
      box-sizing:border-box;border-radius:.5rem;border:1px solid #3a4048;
      background:var(--card);color:var(--txt)}
 #thumbs{display:flex;gap:.4rem;flex-wrap:wrap;margin:.5rem 0}
 #thumbs img{width:4.2rem;height:4.2rem;object-fit:cover;border-radius:.4rem}
 .card{background:var(--card);border-radius:.6rem;padding:.6rem .8rem;margin:.35rem 0;
       display:flex;justify-content:space-between;align-items:center;gap:.5rem}
 .st{font-size:.85rem;padding:.15rem .55rem;border-radius:1rem}
 .st.queued{background:#5f5310}.st.running{background:#0a4a8f}
 .st.done{background:#1c5c2e}.st.failed{background:#7a1f1f}
 .dim{color:var(--dim);font-size:.9rem}
 button.retry{background:none;border:1px solid var(--dim);color:var(--txt);
       border-radius:.4rem;padding:.2rem .6rem}
 nav{display:flex;align-items:center;gap:16px;margin-bottom:1rem} nav a{color:var(--blue)}
 nav b{border-bottom:2px solid var(--blue);padding-bottom:2px}
</style></head><body>
""" + nav("Capture") + """
<div id="connect-banner" style="display:none;background:#5f5310;border-radius:9px;
     padding:10px 14px;margin:10px 0;font-size:14px">
 No vision model connected yet — photos queue up and wait.
 <a href="/setup" style="color:#fff;text-decoration:underline">Connect a model</a>
</div>
<h2>Capture</h2>
<input type="text" id="location" placeholder="location (optional — shoebox is fine)">
<button class="btn" id="shoot">&#128247; Take photo</button>
<button class="btn alt" id="pick">Choose from library</button>
<div id="thumbs"></div>
<button class="btn" id="submit" disabled>Submit bin (0 shots)</button>
<h2 style="margin-top:1.2rem">Scans</h2>
<div id="queue" class="dim">loading…</div>
<input type="file" id="cam" accept="image/*" capture="environment" hidden>
<input type="file" id="lib" accept="image/*" multiple hidden>
<script>
const cam=document.getElementById('cam'), lib=document.getElementById('lib'),
      thumbs=document.getElementById('thumbs'), submit=document.getElementById('submit');
let shots=[];
document.getElementById('shoot').onclick=()=>cam.click();
document.getElementById('pick').onclick=()=>lib.click();
cam.onchange=()=>{add(cam.files);cam.value='';};
lib.onchange=()=>{add(lib.files);lib.value='';};
function add(files){
  for(const f of files){shots.push(f);
    const img=document.createElement('img');
    img.src=URL.createObjectURL(f); thumbs.appendChild(img);}
  submit.disabled=!shots.length;
  submit.textContent=`Submit bin (${shots.length} shot${shots.length==1?'':'s'})`;
}
submit.onclick=async()=>{
  submit.disabled=true; submit.textContent='Submitting…';
  const fd=new FormData();
  for(const f of shots)fd.append('photos',f,f.name||'shot.jpg');
    fd.append('location',document.getElementById('location').value);
  try{
    const r=await fetch('/api/scans',{method:'POST',body:fd});
    if(!r.ok)throw new Error(await r.text());
    shots=[];thumbs.innerHTML='';
    submit.textContent='Submit bin (0 shots)';
    poll();
  }catch(e){alert('submit failed: '+e); submit.disabled=false;}
};
async function poll(){
  try{
    const rows=await (await fetch('/api/queue')).json();
    const q=document.getElementById('queue');
    q.classList.remove('dim');
    q.innerHTML=rows.length?'':'<span class="dim">no scans yet — take a photo</span>';
    for(const r of rows){
      const div=document.createElement('div'); div.className='card';
      const warn=r.retake?' 📷 retake suggested: '+(r.retake_reason||'photo unclear'):'';
      div.innerHTML=`<span>${r.location||'scan '+r.run_id}</span>
        <span class="dim">${r.status=='done'?r.parts+' part(s)'+warn:''}${r.status=='failed'?(r.error||'error').slice(0,60):''}</span>
        <span class="st ${r.status}">${r.status}</span>`;
      if(r.status=='failed'){
        const b=document.createElement('button');b.className='retry';b.textContent='retry';
        b.onclick=async()=>{await fetch('/api/runs/'+r.run_id+'/retry',{method:'POST'});poll();};
        div.appendChild(b);
      }
      q.appendChild(div);
    }
  }catch(e){}
}
poll(); setInterval(poll, 3000);

async function checkBackend(){
  try{
    const s=await (await fetch('/api/setup/status')).json();
    document.getElementById('connect-banner').style.display=s.ready?'none':'block';
  }catch(e){}
}
checkBackend(); setInterval(checkBackend, 5000);
</script></body></html>
"""
