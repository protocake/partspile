"""Browse: the desktop landing page. 4-col square cut-out grid, QR handoff rail,
scans-in-flight, and the part-detail modal (Ben's UI pass v2)."""

from .ui import BASE_CSS, CROP_JS, nav

BROWSE_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parts Pile</title>
<style>""" + BASE_CSS + """
 .layout{display:flex;min-height:calc(100vh - 50px)}
 .main{flex:1;padding:20px 26px;display:flex;flex-direction:column;gap:12px;min-width:0}
 #q{width:100%;font-size:17px;padding:12px 15px;border-radius:10px}
 .filters{display:flex;gap:8px;align-items:center;font-size:13px}
 #grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
 @media(max-width:1000px){#grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
 .card{background:var(--card);border-radius:10px;padding:10px;display:flex;flex-direction:column;
       gap:7px;cursor:pointer}
 .card:hover{outline:1px solid #3a4048}
 .thumb{aspect-ratio:1/1;border-radius:8px;background:var(--inner);width:100%}
 .noimg{display:flex;align-items:center;justify-content:center;color:#3a4048;font-size:12px}
 .cname{font-weight:700;font-size:13px}
 .cfoot{display:flex;align-items:center;font-size:11px;color:var(--dim)}
 .cqty{margin-left:auto;font-size:15px;font-weight:700;color:var(--txt)}
 .rail{width:210px;border-left:1px solid var(--line);padding:16px;display:flex;
       flex-direction:column;gap:12px}
 .qrbox{background:var(--card);border-radius:12px;padding:12px;display:flex;
        flex-direction:column;align-items:center;gap:8px;text-align:center}
 .qrbox img{background:#fff;border-radius:6px;padding:6px;width:110px;height:110px}
 .schip{background:var(--card);border-radius:8px;padding:7px 10px;display:flex;
        justify-content:space-between;align-items:center;font-size:12px;gap:6px}
 .schip span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 #modalwrap{position:fixed;inset:0;display:none;align-items:center;justify-content:center;z-index:10}
 #modalwrap.open{display:flex}
 #backdrop{position:absolute;inset:0;background:rgba(9,11,14,0.6)}
 #modal{position:relative;width:min(960px,94vw);max-height:90vh;overflow:auto;background:var(--card);
        border:1px solid #2c333c;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,0.6);
        display:flex}
 .mphotos{width:360px;flex:none;background:#171b21;padding:18px;display:flex;
          flex-direction:column;gap:10px}
 .mkey{width:100%;aspect-ratio:4/3;border-radius:12px;background:var(--inner)}
 .mstrip{display:flex;gap:8px;flex-wrap:wrap}
 .mstrip .mt{width:70px;height:54px;border-radius:8px;background:var(--inner);cursor:pointer}
 .mstrip .mt.sel{outline:2px solid var(--blue)}
 .mbody{flex:1;padding:20px 22px;display:flex;flex-direction:column;gap:12px;min-width:0}
 .mrow{background:var(--inner);border-radius:10px;padding:10px 13px}
 .mrow .lbl{font-size:11px;color:var(--dim);margin-bottom:4px}
 .mrow input,.mrow textarea{width:100%;background:none;border:none;padding:0;font-size:13px;color:var(--txt)}
 .mrow textarea{resize:vertical;min-height:44px}
 .m2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 .pbar{height:6px;border-radius:3px;background:var(--inner);overflow:hidden;margin-top:8px}
 .pbar i{display:block;height:100%;width:35%;border-radius:3px;background:var(--amber);
   animation:slide 1.2s ease-in-out infinite}
 @keyframes slide{0%{margin-left:-35%}100%{margin-left:100%}}
</style></head><body>
""" + nav("Browse", '<span id="counts"></span>') + """
<div id="welcome-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:50">
 <div style="max-width:560px;margin:8vh auto;background:var(--card);border:1px solid var(--line);
             border-radius:14px;padding:28px 30px;box-shadow:0 18px 60px rgba(0,0,0,.5)">
  <h2 style="margin:0 0 10px;font-size:21px">Welcome to Parts Pile!</h2>
  <p style="font-size:14px;line-height:1.55;color:var(--dim)">This is a small open-source project
   that uses an AI vision model to catalog your electronics parts. There are three sections:</p>
  <ol style="font-size:14px;line-height:1.7;color:var(--txt);padding-left:22px;margin:10px 0 14px">
   <li><b>Browse</b> — your storage area: the collection you're looking at now
       (currently showing a few sample parts so you can see the idea).</li>
   <li><b>Capture</b> — photograph items; each photo is sent to the model automatically.</li>
   <li><b>Review</b> — confirm the model identified each item correctly before it
       joins your collection.</li>
  </ol>
  <p style="font-size:14px;line-height:1.55;color:var(--dim)">To get started, scan the QR code
   with your phone — it opens the camera capture page on this Wi-Fi. The first time through,
   you'll be asked to connect a model: your Claude account or a local open-weight model
   (Claude is the most accurate; local models are free and run entirely on your machine).</p>
  <div style="display:flex;align-items:center;gap:14px;margin-top:18px">
   <button class="b-blue" onclick="dismissWelcome()">Let's go</button>
   <a href="#" onclick="clearSamples(event)" class="dim" style="font-size:13px">remove the sample parts</a>
  </div>
 </div>
</div>
<div class="layout">
 <div class="main">
  <input id="q" placeholder="Do I already have this?  Search parts, notes, serials…" autofocus>
  <div class="filters">
   <select id="category"><option value="">any category</option><option>board</option><option>sensor</option>
    <option>actuator</option><option>display</option><option>power</option><option>passive</option>
    <option>connector</option><option>bare_component</option><option>other</option></select>
   <select id="interface"><option value="">any interface</option><option>i2c</option><option>spi</option>
    <option>uart</option><option>analog</option><option>digital</option><option>onewire</option>
    <option>pwm</option><option>none</option><option>unknown</option></select>
   <select id="group"><option value="">flat</option><option value="location">by location</option><option value="bin">by bin</option></select>
   <a href="/api/export.csv" style="margin-left:auto">CSV export</a>
  </div>
  <div id="empty" class="dim" style="display:none">nothing found</div>
  <div id="grid"></div>
 </div>
 <div class="rail">
  <div class="qrbox">
   <div class="dim" style="font-size:11px;font-weight:600">SCAN WITH YOUR PHONE</div>
   <img id="qr" src="/api/qr.svg" alt="QR to capture page">
   <div id="qrfallback" class="dim" style="font-size:11px;display:none;word-break:break-all"></div>
   <div class="dim" style="font-size:11px;line-height:1.4">opens the capture page<br>on this Wi-Fi</div>
  </div>
  <div>
   <div class="dim" style="font-size:11px;font-weight:600;margin-bottom:6px">SCANS</div>
   <div id="scans" style="display:flex;flex-direction:column;gap:6px"></div>
  </div>
 </div>
</div>
<div id="modalwrap"><div id="backdrop"></div><div id="modal"></div></div>
<script>""" + CROP_JS + """
async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error(await r.text());return r.json();}
let t;
for(const id of ['q','category','interface','group'])
  document.getElementById(id).addEventListener('input',()=>{clearTimeout(t);t=setTimeout(load,200);});
fetch('/api/lan-url').then(r=>r.json()).then(j=>{
  document.getElementById('qr').onerror=()=>{
    document.getElementById('qr').style.display='none';
    const f=document.getElementById('qrfallback');
    f.style.display='block'; f.textContent=j.url+'/capture';
  };
});
async function load(){
  const params=new URLSearchParams({q:q.value,
    category:document.getElementById('category').value,
    interface:document.getElementById('interface').value});
  const rows=await api('/api/parts?'+params);
  const grid=document.getElementById('grid'); grid.innerHTML='';
  document.getElementById('empty').style.display=rows.length?'none':'block';
  const total=rows.reduce((s,r)=>s+r.qty,0);
  document.getElementById('counts').textContent=`${total} pieces · ${rows.length} types`;
  const grouping=document.getElementById('group').value;
  let groups={'':rows};
  if(grouping==='location'){groups={};for(const r of rows)(groups[r.location||'(no location)'] ??= []).push(r);}
  if(grouping==='bin'){groups={};for(const r of rows)(groups[r.bin||'(no bin)'] ??= []).push(r);}
  const tiles=[];
  for(const [g,items] of Object.entries(groups)){
    if(grouping){const h=document.createElement('h3');h.textContent=g;h.style.gridColumn='1/-1';h.style.margin='6px 0 0';grid.appendChild(h);}
    for(const r of items){
      const badge=r.resolution==='undetermined'?' <span class="badge">unverified</span>':'';
      const div=document.createElement('div'); div.className='card';
      div.innerHTML=`<div class="thumb"></div><div class="cname">${r.canonical}${badge}</div>
        <div class="cfoot"><span>${[r.bin,r.location].filter(Boolean).join(' · ')||'<span class="dim">no bin / location</span>'}</span><span class="cqty">×${r.qty}</span></div>`;
      const th=div.querySelector('.thumb');
      if(r.photo){tiles.push({el:th,r});}
      else th.classList.add('noimg'),th.textContent='no photo';
      div.onclick=()=>openModal(r.id);
      grid.appendChild(div);
    }
  }
  // starred photo wins outright; otherwise local guess -> refined crop -> cut-out
  for(const t of tiles)requestAnimationFrame(()=>{
    if(t.r.key_photo_id)cropInto(t.el,'/photos/'+t.r.photo,null);
    else smartThumb(t.el,t.r.id,'/photos/'+t.r.photo,firstBox(t.r));
  });
  const auto=tiles.filter(t=>!t.r.key_photo_id);
  const refined=await refinedBoxes(auto.map(t=>t.r.id));
  for(const t of auto)if(refined[t.r.id]&&!t.el.dataset.cut)cropInto(t.el,'/photos/'+t.r.photo,refined[t.r.id]);
}
async function pollScans(){
  try{
    const rows=await api('/api/queue');
    // only actionable entries: in-flight, failed, or done with parts awaiting review
    const act=rows.filter(r=>r.status!=='done'||r.pending>0);
    const s=document.getElementById('scans'); s.innerHTML='';
    if(!act.length){s.innerHTML='<span class="dim" style="font-size:12px">all clear</span>';return;}
    for(const r of act.slice(0,8)){
      const d=document.createElement('div'); d.className='schip';
      if(r.status==='done'){
        d.style.cursor='pointer';
        const warn=r.retake?' <span class="st queued" title="'+(r.retake_reason||'')+'">📷 retake?</span>':'';
        d.innerHTML=`<span>${r.location||'scan '+r.run_id}</span>${warn}<span class="st done">${r.pending} to review →</span>`;
        d.onclick=()=>{location.href='/review';};
      }else{
        d.innerHTML=`<span>${r.location||'scan '+r.run_id}</span><span class="st ${r.status}">${r.status}</span>`;
        if(r.status==='failed'){const b=document.createElement('button');b.className='b-gray';
          b.style.padding='2px 8px';b.textContent='retry';
          b.onclick=async()=>{await api('/api/runs/'+r.run_id+'/retry',{method:'POST'});pollScans();};
          d.appendChild(b);}
      }
      s.appendChild(d);
    }
  }catch(e){}
}
async function openModal(id){
  const ctx=await api('/api/parts/'+id+'/context');
  const p=ctx.part;
  const wrap=document.getElementById('modalwrap'), m=document.getElementById('modal');
  wrap.classList.add('open');
  const spec=p.spec_url?`<a href="${p.spec_url}" target="_blank">${p.spec_url}</a>`
                       :'<span class="dim">none yet</span>';
  m.innerHTML=`
   <div class="mphotos">
     <div class="mkey" id="mkey"></div>
     <div class="mstrip" id="mstrip"></div>
     <div style="display:flex;gap:6px;flex-wrap:wrap">
       <button class="b-gray" id="maddphoto" style="padding:5px 10px;font-size:12px">+ add photo</button>
       <button class="b-gray" id="msuggest" style="padding:5px 10px;font-size:12px">🖼 from product page</button>
       <input type="file" id="maddinput" accept="image/*" multiple hidden>
     </div>
     <div id="msuggestslot"></div>
     <div class="dim" style="font-size:11px;line-height:1.4">click to view · ★ chooses the thumbnail (the cut-out counts as one)</div>
   </div>
   <div class="mbody">
     <div style="display:flex;align-items:flex-start;gap:10px">
       <div><div style="font-size:21px;font-weight:800">${p.canonical}
         <span class="dim" style="font-size:13px;font-weight:400">×${p.qty} in inventory</span></div>
         <div class="dim" style="font-size:13px;margin-top:2px">${p.name} · ${p.category}</div></div>
       <button class="b-gray" style="margin-left:auto" id="mclose">✕</button>
     </div>
     <div class="mrow" style="display:flex;align-items:center;gap:10px">
       <div style="flex:1;min-width:0"><div class="lbl">PRODUCT PAGE</div>
         <div id="specshow">${spec}</div>
         <input id="mspec" placeholder="paste URL…" value="${p.spec_url||''}" style="margin-top:4px">
         <div id="guess-spec_url"></div></div>
       <div style="display:flex;flex-direction:column;gap:6px">
         <button class="b-blue" id="mlookup">🔎 look up</button>
         <button class="b-amber" id="mguess">✨ best guess</button>
       </div>
     </div>
     <div class="m2">
       <div class="mrow"><div class="lbl">BIN <span style="font-weight:400">— which container this part lives in</span></div>
         <input id="mbin" placeholder="e.g. bin 12" value="${p.bin||''}"></div>
       <div class="mrow"><div class="lbl">SERIAL NUMBER</div><input id="mserial" placeholder="add…" value="${p.serial||''}">
         <div id="guess-serial"></div></div>
       <div class="mrow"><div class="lbl">QUANTITY</div><input id="mqty" type="number" min="1" value="${p.qty}"></div>
       <div class="mrow" style="grid-column:1/-1"><div class="lbl">LOCATION <span style="font-weight:400">— applies to everything scanned together</span></div>
         <input id="mloc" placeholder="shoebox, drawer, shelf…" value="${ctx.scan.location||''}"></div>
     </div>
     <div class="mrow"><div class="lbl">NOTES</div><textarea id="mnotes" placeholder="anything worth remembering about this item…">${p.notes||''}</textarea></div>
     <div style="display:flex;gap:10px;align-items:center;margin-top:auto">
       <span class="dim" style="font-size:12px">scanned by ${p.canonical?'':''}${ctx.provenance}</span>
       <button class="b-green" style="margin-left:auto" id="msave">save</button>
     </div>
   </div>`;
  const key=document.getElementById('mkey');
  const strip=document.getElementById('mstrip');
  let starred=p.key_photo_id; // null => auto (the cut-out)
  function showBig(src,contain){
    key.replaceChildren();
    if(contain){const im=new Image();im.src=src;im.style.cssText='width:100%;height:100%;object-fit:contain';
      key.style.overflow='hidden';key.appendChild(im);}
    else requestAnimationFrame(()=>cropInto(key,src,null));
  }
  async function setStar(photoId){
    starred=photoId;
    await api('/api/parts/'+p.id,{method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({key_photo_id:photoId})});
    renderStrip();
  }
  function tile(starId,render,onview,label){
    const d=document.createElement('div'); d.className='mt'; d.style.position='relative';
    render(d); d.onclick=onview;
    const st=document.createElement('button');
    st.textContent=(starred===starId)?'★':'☆';
    st.title='use as thumbnail';
    st.style.cssText='position:absolute;right:2px;top:2px;border:none;border-radius:6px;'+
      'padding:0 4px;font-size:12px;cursor:pointer;background:rgba(17,20,24,.75);'+
      'color:'+((starred===starId)?'#e8b93e':'#9aa0a6');
    st.onclick=(e)=>{e.stopPropagation();setStar(starId);};
    d.appendChild(st);
    if(label){const b=document.createElement('span');
      b.textContent=label;
      b.style.cssText='position:absolute;left:2px;bottom:2px;font-size:9px;background:rgba(17,20,24,.75);'+
        'border-radius:5px;padding:0 4px;color:#9aa0a6';d.appendChild(b);}
    return d;
  }
  function renderStrip(){
    strip.innerHTML='';
    // the cut-out is one of the images; starring it = automatic thumbnail mode
    const cutUrl='/api/cutouts/'+p.id+'.png';
    const cd=tile(null,(d)=>{const im=new Image();im.src=cutUrl;
        im.style.cssText='width:100%;height:100%;object-fit:contain';
        im.onerror=()=>{cd.style.display='none';};d.appendChild(im);},
      ()=>showBig(cutUrl,true),'cut-out');
    strip.appendChild(cd);
    for(const ph of ctx.photos){
      const d=tile(ph.id,
        (el)=>requestAnimationFrame(()=>cropInto(el,'/photos/'+ph.file,null)),
        ()=>showBig('/photos/'+ph.file,false),
        ph.kind==='catalog'?'catalog':null);
      const del=document.createElement('button');
      del.textContent='✕'; del.title='delete this photo';
      del.style.cssText='position:absolute;left:2px;top:2px;border:none;border-radius:6px;'+
        'padding:0 4px;font-size:11px;cursor:pointer;background:rgba(122,31,31,.85);color:#fff';
      del.onclick=async(e)=>{e.stopPropagation();
        const msg=ph.shared
          ?'This is an original scan photo shared by every part from that scan. Delete it for all of them?'
          :'Delete this photo?';
        if(!confirm(msg))return;
        await api('/api/photos/'+ph.id,{method:'DELETE'});
        openModal(p.id); load();
      };
      d.appendChild(del);
      strip.appendChild(d);
    }
  }
  const kf=ctx.photos.find(x=>x.id===starred);
  if(kf)showBig('/photos/'+kf.file,false);
  else showBig('/api/cutouts/'+p.id+'.png',true);
  renderStrip();
  document.getElementById('maddphoto').onclick=()=>document.getElementById('maddinput').click();
  document.getElementById('maddinput').onchange=async(e)=>{
    const fd=new FormData();
    for(const f of e.target.files)fd.append('photos',f,f.name||'photo.jpg');
    await fetch('/api/parts/'+p.id+'/photos',{method:'POST',body:fd});
    openModal(p.id);
  };
  const sug=document.getElementById('msuggest');
  if(!p.spec_url){sug.disabled=true;sug.title='add a product page URL first';}
  sug.onclick=async()=>{
    sug.disabled=true;sug.textContent='fetching…';
    const slot=document.getElementById('msuggestslot');
    try{
      const r=await api('/api/parts/'+p.id+'/suggest-image',{method:'POST'});
      slot.innerHTML='';
      const row=document.createElement('div');
      row.style.cssText='margin-top:6px;padding:7px;border:1px dashed #e8b93e;border-radius:8px';
      row.innerHTML=`<img src="${r.preview}?t=${Date.now()}" style="max-width:100%;max-height:120px;border-radius:6px;display:block;margin-bottom:5px">
        <span class="dim" style="font-size:11px;word-break:break-all">${r.source}</span><br>`;
      const ok=document.createElement('button');ok.className='b-green';
      ok.style.cssText='padding:3px 10px;margin-top:5px';ok.textContent='✓ add to photos';
      ok.onclick=async()=>{await api('/api/parts/'+p.id+'/adopt-suggestion',{method:'POST'});openModal(p.id);};
      const no=document.createElement('button');no.className='b-gray';
      no.style.cssText='padding:3px 10px;margin:5px 0 0 6px';no.textContent='✕';
      no.onclick=()=>{slot.innerHTML='';};
      row.appendChild(ok);row.appendChild(no);slot.appendChild(row);
      sug.textContent='🖼 from product page';
    }catch(e){sug.textContent='no image found — retry';}
    sug.disabled=!p.spec_url?true:false;
  };
  document.getElementById('mclose').onclick=close;
  document.getElementById('backdrop').onclick=close;
  document.getElementById('mlookup').onclick=()=>window.open(
    'https://duckduckgo.com/?q='+encodeURIComponent(p.canonical+' datasheet product page'),'_blank');
  const guessBtn=document.getElementById('mguess');
  guessBtn.onclick=async()=>{
    guessBtn.disabled=true; guessBtn.textContent='guessing…';
    const prog=document.createElement('div');
    prog.innerHTML=`<div class="pbar"><i></i></div>
      <div class="dim" style="font-size:11px;margin-top:3px">reading photos &amp; searching the web… <span id="gsecs">0</span>s (usually 20–60s)</div>`;
    document.getElementById('guess-spec_url').replaceChildren(prog);
    const t0=Date.now();
    const tick=setInterval(()=>{const e=document.getElementById('gsecs');
      if(e)e.textContent=Math.round((Date.now()-t0)/1000);},1000);
    try{
      const g=await api('/api/parts/'+p.id+'/guess',{method:'POST'});
      let any=false;
      for(const field of ['spec_url','serial']){
        const slot=document.getElementById('guess-'+field); slot.innerHTML='';
        if(!g[field]){
          if(g[field+'_note'])slot.innerHTML=`<div class="dim" style="font-size:11px;margin-top:5px">AI: ${g[field+'_note']}</div>`;
          continue;
        }
        any=true;
        const row=document.createElement('div');
        row.style.cssText='margin-top:6px;padding:7px 9px;border:1px dashed #e8b93e;border-radius:8px;font-size:12px';
        const shown=field==='spec_url'
          ?`<a href="${g[field]}" target="_blank" style="word-break:break-all">${g[field]}</a>`
          :`<span style="word-break:break-all">${g[field]}</span>`;
        row.innerHTML=`<div>✨ ${shown}</div>
          <div class="dim" style="font-size:11px;margin:3px 0">${g[field+'_note']||''}</div>`;
        const ok=document.createElement('button'); ok.className='b-green';
        ok.style.padding='3px 10px'; ok.textContent='✓ confirm';
        ok.onclick=async()=>{
          document.getElementById(field==='serial'?'mserial':'mspec').value=g[field];
          await api('/api/parts/'+p.id,{method:'PATCH',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({[field]:g[field]})});
          row.innerHTML=`<span style="color:#34a853">✓ confirmed & saved</span>`
            +(field==='spec_url'?` · <a href="${g[field]}" target="_blank">open page</a>`:'');
          if(field==='spec_url')document.getElementById('specshow').innerHTML=
            `<a href="${g[field]}" target="_blank">${g[field]}</a>`;
        };
        const no=document.createElement('button'); no.className='b-gray';
        no.style.cssText='padding:3px 10px;margin-left:6px'; no.textContent='✕';
        no.onclick=()=>row.remove();
        row.appendChild(ok); row.appendChild(no);
        slot.appendChild(row);
      }
      guessBtn.textContent=any?'✨ best guess':'nothing found';
    }catch(e){guessBtn.textContent='guess failed — retry';
      document.getElementById('guess-spec_url').innerHTML='';}
    clearInterval(tick);
    guessBtn.disabled=false;
  };
  document.getElementById('msave').onclick=async()=>{
    await api('/api/parts/'+p.id,{method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({serial:document.getElementById('mserial').value,
        notes:document.getElementById('mnotes').value,
        qty:parseInt(document.getElementById('mqty').value)||p.qty,
        bin:document.getElementById('mbin').value,
        spec_url:document.getElementById('mspec').value})});
    await api('/api/scans/'+ctx.scan.id,{method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({location:document.getElementById('mloc').value})});
    close(); load();
  };
  function close(){wrap.classList.remove('open');}
  document.onkeydown=(e)=>{if(e.key==='Escape')close();};
}
load(); pollScans(); setInterval(pollScans,4000);

// First-run welcome overlay (dismiss persists in this browser).
if(!localStorage.getItem('pp_welcomed')){
  document.getElementById('welcome-overlay').style.display='block';
}
function dismissWelcome(){
  localStorage.setItem('pp_welcomed','1');
  document.getElementById('welcome-overlay').style.display='none';
}
async function clearSamples(e){
  e.preventDefault();
  await fetch('/api/samples/clear',{method:'POST'});
  dismissWelcome(); load();
}
</script></body></html>
"""
