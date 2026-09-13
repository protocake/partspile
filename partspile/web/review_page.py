"""Review: full shot left with bbox spotlight, per-part cut-out cards right
(Ben's UI pass v2 — cut-outs instead of circles)."""

from .ui import BASE_CSS, CROP_JS, nav

REVIEW_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parts Pile — review</title>
<style>""" + BASE_CSS + """
 .wrap{max-width:1200px;margin:0 auto;padding:18px 22px}
 .binrow{display:flex;gap:20px;margin-bottom:26px;align-items:flex-start}
 @media(max-width:900px){.binrow{flex-direction:column}}
 .photos{flex:1.15;min-width:0;position:sticky;top:12px}
 .mainshot{position:relative;border-radius:12px;overflow:hidden;background:#000}
 .mainshot img{width:100%;display:block}
 .ring{position:absolute;border-radius:12px;pointer-events:none;opacity:0;transition:opacity .15s}
 .ring.ok{border:3px solid var(--green)}
 .ring.warn{border:3px dashed var(--amber)}
 .ring.active{opacity:1;box-shadow:0 0 0 2000px rgba(0,0,0,0.4)}
 .shots{display:flex;gap:8px;margin-top:8px;align-items:center}
 .shots .mt{width:64px;height:48px;border-radius:6px;background:var(--inner);cursor:pointer}
 .shots .mt.sel{outline:2px solid var(--blue)}
 .parts{flex:1;display:flex;flex-direction:column;gap:9px;min-width:0}
 .part{background:var(--card);border-radius:10px;padding:11px 13px;display:flex;gap:12px;
       align-items:flex-start}
 .part.warn{border:1px solid var(--amber)}
 .cut{width:84px;height:68px;border-radius:8px;flex:none;background:var(--inner)}
 .part.warn .cut{outline:2px dashed var(--amber)}
 .pname{font-weight:700;font-size:14px}
 .pmeta{color:var(--dim);font-size:12px}
 .pwarn{color:var(--amber);font-size:12px;line-height:1.45;margin-top:2px}
 .have{color:#7ec8ff;font-size:12px}
 .row{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
 .editform{margin-top:8px;display:flex;flex-direction:column;gap:5px}
 .editform input,.editform select{width:100%}
 h3{margin:4px 0 8px}
</style></head><body>
""" + nav("Review") + """
<div class="wrap"><div id="bins"><span class="dim">loading…</span></div></div>
<script>""" + CROP_JS + """
async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error(await r.text());return r.json();}
function specSearch(c){return 'https://duckduckgo.com/?q='+encodeURIComponent(c+' datasheet');}
async function load(){
  const bins=await api('/api/review');
  const root=document.getElementById('bins'); root.innerHTML='';
  if(!bins.length){root.innerHTML='<span class="dim">nothing pending — go scan something</span>';return;}
  for(const b of bins){
    const h=document.createElement('h3');
    h.textContent=b.location||'unfiled scan'; root.appendChild(h);
    const row=document.createElement('div'); row.className='binrow';
    const photoFile=b.photos[0]?b.photos[0].file:null;
    const left=document.createElement('div'); left.className='photos';
    left.innerHTML=`<div class="mainshot"><img id="main-${b.scan_id}" src="${photoFile?'/photos/'+photoFile:''}"></div>
      <div class="shots" id="shots-${b.scan_id}"></div>`;
    row.appendChild(left);
    const main=left.querySelector('.mainshot');
    const shots=left.querySelector('.shots');
    for(const ph of b.photos){
      const t=document.createElement('div'); t.className='mt'+(ph.file===photoFile?' sel':'');
      requestAnimationFrame(()=>cropInto(t,'/photos/'+ph.file,null));
      t.onclick=()=>{left.querySelector('img').src='/photos/'+ph.file;
        for(const x of shots.children)x.classList.remove('sel');t.classList.add('sel');};
      shots.appendChild(t);
    }
    const addBtn=document.createElement('button'); addBtn.className='b-blue'; addBtn.textContent='📷 add angle';
    const inp=document.createElement('input'); inp.type='file'; inp.accept='image/*';
    inp.setAttribute('capture','environment'); inp.hidden=true;
    addBtn.onclick=()=>inp.click();
    inp.onchange=async()=>{const fd=new FormData();
      for(const f of inp.files)fd.append('photos',f,f.name||'shot.jpg');
      await fetch('/api/scans/'+b.scan_id+'/photos',{method:'POST',body:fd});
      addBtn.textContent='✓ re-scan queued'; inp.value='';};
    shots.appendChild(addBtn); shots.appendChild(inp);
    const partsCol=document.createElement('div'); partsCol.className='parts';
    const refined=await refinedBoxes(b.parts.map(p=>p.id));
    for(const p of b.parts){
      const box=refined[p.id]||firstBox(p);
      let ring=null;
      if(box&&photoFile){
        ring=document.createElement('div');
        ring.className='ring '+(p.needs_reshoot?'warn':'ok');
        ring.style.left=(box.x*100)+'%'; ring.style.top=(box.y*100)+'%';
        ring.style.width=(box.w*100)+'%'; ring.style.height=(box.h*100)+'%';
        main.appendChild(ring);
      }
      const div=document.createElement('div');
      div.className='part'+(p.needs_reshoot?' warn':'');
      const warn=p.needs_reshoot?`<div class="pwarn">⚠ ${p.reshoot_reason||'needs another angle'}</div>`:'';
      const have=p.have>0?`<div class="have">you already have ${p.have} of these</div>`:'';
      div.innerHTML=`<div class="cut"></div><div style="flex:1;min-width:0">
        <div class="pname">${p.canonical} <span class="pmeta">×${p.qty} · ${p.confidence}</span></div>
        <div class="pmeta">${p.name}</div>${warn}${have}
        <div class="row">
          <button class="b-green act-accept">accept</button>
          <button class="b-gray act-edit">edit</button>
          <button class="b-amber act-giveup">can't determine</button>
          <button class="b-red act-del">delete</button>
          <a href="${specSearch(p.canonical)}" target="_blank" style="align-self:center;font-size:12px">datasheet</a>
        </div></div>`;
      const cut=div.querySelector('.cut');
      if(photoFile)requestAnimationFrame(()=>smartThumb(cut,p.id,'/photos/'+photoFile,box));
      if(ring){div.onmouseenter=()=>ring.classList.add('active');
               div.onmouseleave=()=>ring.classList.remove('active');}
      div.querySelector('.act-accept').onclick=async()=>{await api('/api/parts/'+p.id+'/accept',{method:'POST'});load();};
      div.querySelector('.act-del').onclick=async()=>{await api('/api/parts/'+p.id,{method:'DELETE'});load();};
      div.querySelector('.act-giveup').onclick=async()=>{await api('/api/parts/'+p.id+'/undetermined',{method:'POST'});load();};
      div.querySelector('.act-edit').onclick=()=>{
        if(div.querySelector('.editform'))return;
        const f=document.createElement('div'); f.className='editform';
        f.innerHTML=`<input name="canonical" value="${p.canonical}" placeholder="canonical">
          <input name="name" value="${p.name}" placeholder="name">
          <input name="qty" type="number" min="1" value="${p.qty}">
          <select name="category"><option>board</option><option>sensor</option><option>actuator</option>
           <option>display</option><option>power</option><option>passive</option><option>connector</option>
           <option>bare_component</option><option>other</option></select>
          <input name="bin" value="${p.bin||''}" placeholder="bin (which container, optional)">
          <input name="serial" value="${p.serial||''}" placeholder="serial number (optional)">
          <input name="notes" value="${(p.notes||'').replace(/"/g,'&quot;')}" placeholder="note about this item">
          <input name="spec_url" value="${p.spec_url||''}" placeholder="spec page URL (optional)">
          <div class="row"><button class="b-green">save</button><button class="b-gray">cancel</button></div>`;
        f.querySelector('select').value=p.category;
        f.querySelector('.b-green').onclick=async()=>{
          const v=(n)=>f.querySelector(`[name=${n}]`).value;
          await api('/api/parts/'+p.id,{method:'PATCH',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({canonical:v('canonical'),name:v('name'),
              qty:parseInt(v('qty'))||1,category:v('category'),bin:v('bin'),serial:v('serial'),
              notes:v('notes'),spec_url:v('spec_url')})});
          load();};
        f.querySelector('.b-gray').onclick=()=>f.remove();
        div.lastElementChild.appendChild(f);
      };
      partsCol.appendChild(div);
    }
    const acceptAll=document.createElement('button'); acceptAll.className='b-green';
    acceptAll.textContent='accept all clear parts';
    acceptAll.onclick=async()=>{
      for(const p of b.parts)if(!p.needs_reshoot)await api('/api/parts/'+p.id+'/accept',{method:'POST'});
      load();};
    partsCol.appendChild(acceptAll);
    row.appendChild(partsCol);
    root.appendChild(row);
  }
}
load();
</script></body></html>
"""
