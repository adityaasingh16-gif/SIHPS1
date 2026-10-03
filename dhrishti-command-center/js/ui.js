/* DHRISHTI UI primitives — toasts, charts (dependency-free SVG), csv, a11y */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function toast(msg,type='info'){const t=document.createElement('div');t.className='toast '+type;t.textContent=msg;$('#toasts').appendChild(t);setTimeout(()=>{t.style.opacity='0';setTimeout(()=>t.remove(),250)},4200)}
  function say(msg){$('#srLive').textContent=msg}
  function countUp(el,to,{suffix='',dur=700}={}){const red=matchMedia('(prefers-reduced-motion: reduce)').matches;if(red){el.textContent=fmt(to)+suffix;return}const t0=performance.now();(function f(t){const p=Math.min(1,(t-t0)/dur);el.textContent=fmt(Math.round(to*(0.2+0.8*p)*10)/10).replace(/\.0$/,'')+suffix;if(p<1)requestAnimationFrame(f)})(t0)}
  const fmt=n=>Number(n).toLocaleString('en-IN');
  function riskBadge(l){const m={CRITICAL:'red',HIGH:'amber',MODERATE:'blue',STABLE:'green'};return `<span class="badge ${m[l]||'grey'}"><span class="dot" style="background:currentColor"></span>${esc(l)}</span>`}
  function donut(score,size=120){const r=52,c=2*Math.PI*r,off=c*(1-Math.min(100,score)/100);const col=score>=85?'#dc2626':score>=65?'#d97706':score>=40?'#0284c7':'#16a34a';
    return `<svg class="risk-ring" viewBox="0 0 120 120" role="img" aria-label="Risk score ${score} of 100"><circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--border)" stroke-width="12"/><circle cx="60" cy="60" r="${r}" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 60 60)"/><text x="60" y="58" text-anchor="middle" font-size="24" font-weight="800" fill="var(--text)">${score}</text><text x="60" y="74" text-anchor="middle" font-size="10" fill="var(--muted)">/ 100</text></svg>`}
  function spark(vals,w=120,h=30,col='var(--primary)'){const mx=Math.max(...vals,1),mn=Math.min(...vals,0);const pts=vals.map((v,i)=>`${(i/(vals.length-1||1)*w).toFixed(1)},${(h-3-((v-mn)/(mx-mn||1))*(h-8)).toFixed(1)}`).join(' ');
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2" stroke-linecap="round"/></svg>`}
  function bars(rows,{vl=0}={}){const mx=Math.max(...rows.map(r=>r.v),1);return rows.map(r=>`<div class="contrib-row"><span>${esc(r.k)}</span><div class="contrib-bar"><i style="width:${Math.round(r.v/mx*100)}%"></i></div><b>${r.v}${vl||''}</b></div>`).join('')}
  function lineChart(series,{w=560,h=200,labels=[]}={}){const all=series.flatMap(s=>s.data.filter(v=>v!=null));const mx=Math.max(...all,1),mn=Math.min(...all,0);
    const X=i=>30+(i/((labels.length||series[0].data.length)-1||1)*(w-50));const Y=v=>10+((mx-v)/(mx-mn||1)*(h-40));
    let grids='';for(let g=0;g<4;g++){const y=14+g*((h-44)/3);grids+=`<line x1="30" y1="${y}" x2="${w-8}" y2="${y}" stroke="var(--border)" stroke-width="1" opacity=".6"/>`}
    const paths=series.map(s=>{const pts=s.data.map((v,i)=>v==null?null:`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).filter(Boolean);const d='M'+pts.join(' L');
      const area=`${d} L${X(s.data.length-1).toFixed(1)},${h-24} L30,${h-24} Z`;
      return `${s.fill?`<path d="${area}" fill="${s.color}" opacity=".14"/>`:''}<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="${s.dash||''}"/>`}).join('');
    const dots=series[0].data.map((v,i)=>v==null?'':`<circle cx="${X(i)}" cy="${Y(v)}" r="3.4" fill="${series[0].color}"><title>${esc(labels[i]||('P'+i))}: ${v}</title></circle>`).join('');
    const xl=labels.map((l,i)=>`<text x="${X(i)}" y="${h-6}" font-size="10" text-anchor="middle" fill="var(--muted)">${esc(l)}</text>`).join('');
    const leg=series.map(s=>`<span style="color:${s.color}">●</span> ${esc(s.name)}`).join('&nbsp;&nbsp;');
    return `<div style="font-size:12px;color:var(--muted);margin-bottom:6px">${leg}</div><svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto" role="img" aria-label="${esc(series.map(s=>s.name).join(', '))}">${grids}${paths}${dots}${xl}</svg>`}
  function donutSplit(parts){const tot=parts.reduce((a,b)=>a+b.v,0)||1;let a0=0;const R=54,C=110;const segs=parts.map(p=>{const frac=p.v/tot;const s=`<circle cx="60" cy="60" r="${R}" fill="none" stroke="${p.c}" stroke-width="14" stroke-dasharray="${(frac*C*2*Math.PI/100).toFixed(1)} ${(C*2*Math.PI/100).toFixed(1)}" stroke-dashoffset="${(-a0*C*2*Math.PI/100).toFixed(1)}" transform="rotate(-90 60 60)"/>`;a0+=frac*100;return s}).join('');
    return `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><svg width="130" height="130" viewBox="0 0 120 120" role="img" aria-label="Distribution">${segs}<text x="60" y="66" text-anchor="middle" font-size="20" font-weight="800" fill="var(--text)">${tot}</text></svg><div>${parts.map(p=>`<div style="font-size:12.5px;margin:4px 0"><span style="color:${p.c}">●</span> ${esc(p.k)} — <b>${p.v}</b></div>`).join('')}</div></div>`}
  function skeleton(n=3){return Array.from({length:n},()=>'<div class="skel" style="height:56px;margin:8px 0"></div>').join('')}
  function emptyState(title,sub,actions=''){return `<div class="empty"><div class="e-ic">◌</div><h3>${esc(title)}</h3><p>${esc(sub)}</p><div class="row" style="justify-content:center;margin-top:12px">${actions}</div></div>`}
  function errorState(msg,retry){return `<div class="status error">⚠ ${esc(msg)}</div><div class="row"><button class="btn sm" data-retry="${retry||''}">Retry</button><button class="btn ghost sm" data-view="dashboard">Go to Dashboard</button></div>`}
  function toCSV(rows){if(!rows.length)return '';const cols=Object.keys(rows[0]);const q=v=>`"${String(v??'').replace(/"/g,'""')}"`;return cols.join(',')+'\n'+rows.map(r=>cols.map(c=>q(r[c])).join(',')).join('\n')}
  function download(name,content,type='text/csv'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}
  window.DHRISHTI_UI={$,$$,esc,toast,say,countUp,fmt,riskBadge,donut,spark,bars,lineChart,donutSplit,skeleton,emptyState,errorState,toCSV,download};
})();
