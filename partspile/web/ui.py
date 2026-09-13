"""Shared UI fragments: base styles, nav, and the bbox crop helper (vanilla JS).

The crop helper is the heart of Ben's cut-out idea: every part thumbnail is the
original capture clipped to the model's bounding box — pure CSS/JS, no server-side
image processing, and the full-context photo is always one interaction away.
"""

BASE_CSS = """
 :root{--blue:#0a74da;--bg:#111418;--card:#1c2128;--inner:#12161b;--txt:#e8eaed;
       --dim:#9aa0a6;--line:#262c34;--green:#34a853;--amber:#e8b93e}
 *{box-sizing:border-box}
 body{font-family:-apple-system,system-ui,sans-serif;margin:0;background:var(--bg);color:var(--txt)}
 a{color:var(--blue);text-decoration:none}
 nav{display:flex;align-items:center;gap:22px;padding:13px 26px;border-bottom:1px solid var(--line)}
 nav .brand{font-weight:700;font-size:16px}
 nav a,nav b{font-size:14px}
 nav b{border-bottom:2px solid var(--blue);padding-bottom:3px}
 nav .right{margin-left:auto;color:var(--dim);font-size:13px}
 button{border:none;border-radius:7px;padding:8px 14px;font-size:13px;color:#fff;cursor:pointer}
 .b-blue{background:var(--blue)}.b-green{background:#1c5c2e}.b-gray{background:#3a4048}
 .b-red{background:#7a1f1f}.b-amber{background:#5f5310}
 input,select,textarea{font-size:13px;padding:8px 10px;border-radius:8px;border:1px solid #3a4048;
   background:var(--inner);color:var(--txt)}
 .st{font-size:11px;padding:2px 8px;border-radius:12px}
 .st.queued{background:#5f5310}.st.running{background:#0a4a8f}
 .st.done{background:#1c5c2e}.st.failed{background:#7a1f1f}
 .badge{font-size:11px;padding:1px 7px;border-radius:10px;background:#5f5310}
 .dim{color:var(--dim)}
"""

CROP_JS = """
// Fill `el` (fixed-size, overflow:hidden, position:relative) with photoUrl clipped
// to bbox {x,y,w,h} (normalized 0-1). Falls back to cover when bbox is missing.
function cropInto(el, photoUrl, bbox){
  el.style.overflow='hidden'; el.style.position='relative';
  const img=document.createElement('img');
  img.src=photoUrl; img.style.position='absolute'; img.style.maxWidth='none';
  img.onload=()=>{
    const W=el.clientWidth,H=el.clientHeight,nw=img.naturalWidth,nh=img.naturalHeight;
    if(!bbox||!(bbox.w>0)||!(bbox.h>0)){ // cover fallback
      const s=Math.max(W/nw,H/nh);
      img.style.width=(nw*s)+'px';
      img.style.left=((W-nw*s)/2)+'px'; img.style.top=((H-nh*s)/2)+'px';
      return;
    }
    const pad=0.12; // breathing room around the box
    const bw=Math.min(1,bbox.w*(1+2*pad)), bh=Math.min(1,bbox.h*(1+2*pad));
    const bx=Math.max(0,Math.min(1-bw,bbox.x-bbox.w*pad));
    const by=Math.max(0,Math.min(1-bh,bbox.y-bbox.h*pad));
    const s=Math.max(W/(nw*bw),H/(nh*bh)); // cover the tile with the padded box
    img.style.width=(nw*s)+'px';
    const cx=(bx+bw/2)*nw*s, cy=(by+bh/2)*nh*s;
    img.style.left=Math.min(0,Math.max(W-nw*s,W/2-cx))+'px';
    img.style.top=Math.min(0,Math.max(H-nh*s,H/2-cy))+'px';
  };
  el.replaceChildren(img);
}
function firstBox(part){
  try{const b=JSON.parse(part.bbox_json||'[]');return b.length?b[0]:null}catch(e){return null}
}
// Best thumbnail: paint the rectangle crop immediately, then upgrade to the
// transparent cut-out (Apple subject lifting) when the server produces one.
function smartThumb(el, partId, photoUrl, localBox){
  cropInto(el, photoUrl, localBox);
  const im=new Image();
  im.onload=()=>{
    el.dataset.cut='1';
    im.style.width='100%'; im.style.height='100%'; im.style.objectFit='contain';
    el.replaceChildren(im);
  };
  im.src='/api/cutouts/'+partId+'.png';
}
// Batch-fetch server-segmented tight boxes; {} on failure so callers fall back.
async function refinedBoxes(ids){
  if(!ids.length)return {};
  try{const r=await fetch('/api/refined-boxes?ids='+ids.join(','));
      return r.ok?await r.json():{}}catch(e){return {}}
}
"""


def nav(active: str, right: str = "") -> str:
    items = [("Browse", "/"), ("Review", "/review"), ("Capture", "/capture")]
    links = "".join(
        f"<b>{name}</b>" if name == active else f'<a href="{href}">{name}</a>'
        for name, href in items)
    return (f'<nav><span class="brand">Parts Pile</span>{links}'
            f'<span class="right">{right}</span></nav>')
