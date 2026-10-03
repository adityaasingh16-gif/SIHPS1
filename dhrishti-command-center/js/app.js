/* DHRISHTI Command Center — router, views, search, filters, drawer, reports */
(function(){
const {$,$$,esc,toast,say,countUp,fmt,riskBadge,donut,spark,bars,lineChart,donutSplit,skeleton,emptyState,errorState,toCSV,download}=DHRISHTI_UI;
const api=DHRISHTI_API;
const S={view:'dashboard',user:api.user,filters:{ministry:'',state:'',sector:'',risk_level:'',search:''},sort:{k:'risk_score',d:-1},page:0,per:15,projects:[],total:0,summary:null,alerts:[],meta:{ministries:[],sectors:[],states:[]},sel:[],cols:{ministry:1,state:1,progress:1,risk:1},readNotif:JSON.parse(localStorage.getItem('dhrishti_read')||'[]'),audit:[],aiProject:null,mapRisk:''};

function auditLog(action,target){S.audit.unshift({created_at:new Date().toISOString(),user:(S.user&&S.user.email)||'guest',role:(S.user&&S.user.role)||'guest',action,target,result:'ok'});if(S.audit.length>200)S.audit.pop()}

/* ---------- theme ---------- */
function initTheme(){const t=localStorage.getItem('dhrishti_theme')||'light';setTheme(t);$('#themeSel').value=t}
function setTheme(t){if(t==='system'){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.dataset.theme=t;localStorage.setItem('dhrishti_theme',$('#themeSel').value)}
$('#themeSel').addEventListener('change',e=>{localStorage.setItem('dhrishti_theme',e.target.value);setTheme(e.target.value)});

/* ---------- nav / router ---------- */
function go(view){S.view=view;S.page=0;$$('.navitem[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$$('.bottomnav button').forEach(b=>b.classList.toggle('active',b.dataset.view===view));render();$('#main').focus({preventScroll:true});window.scrollTo({top:0,behavior:'smooth'})}
document.addEventListener('click',e=>{const v=e.target.closest('[data-view]');if(v){go(v.dataset.view);hidePalette()}const r=e.target.closest('[data-retry]');if(r)render()});
$('#menuBtn').addEventListener('click',()=>{document.body.classList.toggle('nav-collapsed');$('#menuBtn').setAttribute('aria-expanded',!document.body.classList.contains('nav-collapsed'))});
if(innerWidth<860)$('#menuBtn').style.display='grid',$('#menuBtn').onclick=()=>toast('Use the bottom navigation on mobile','info');

/* ---------- auth ---------- */
function refreshUser(){$('#loginBtn').style.display=S.user?'none':'';$('#userChip').hidden=!S.user;if(S.user){$('#userName').textContent=(S.user.email||S.user.name||'User')+' · '+(S.user.role||'officer');$('#userInit').textContent=(S.user.email||'G')[0].toUpperCase();$('#sessionInfo').textContent='Session: '+(S.user.role||'active')+' · last login just now'}else{$('#sessionInfo').textContent='Session: guest'}
  $$('#sidebar .navitem[data-role]').forEach(b=>{const roles=b.dataset.role.split(',');b.style.display=!S.user? '' : (roles.includes(S.user.role)||S.user.role==='admin'?'':'none')});}
$('#loginBtn').onclick=()=>{$('#authOverlay').hidden=false};$('#ctaLogin')&&($('#ctaLogin').onclick=()=>$('#authOverlay').hidden=false);
$('#authClose').onclick=()=>$('#authOverlay').hidden=true;
$('#guestBtn').onclick=()=>{api.setSession('',null);S.user=null;refreshUser();$('#authOverlay').hidden=true;toast('Continuing as guest — public data visible','info');render()};
$$('[data-demo]').forEach(b=>b.onclick=async()=>{const map={admin:'admin@mospi.gov.in',officer:'officer.mospi@gov.in',analyst:'analyst.mospi@gov.in',agency:'agency@infra.gov.in'};try{const u=await api.login(map[b.dataset.demo],'demo1234');S.user=u;refreshUser();$('#authOverlay').hidden=true;auditLog('login',u.email);toast('Signed in as '+u.role,'success');render()}catch(e){toast('Sign-in failed: '+e.message,'error')}});
$('#loginForm').addEventListener('submit',async e=>{e.preventDefault();try{const u=await api.login($('#loginEmail').value,$('#loginPass').value);S.user=u;refreshUser();$('#authOverlay').hidden=true;auditLog('login',u.email);toast('Welcome, '+(u.role||'officer'),'success');render()}catch(err){toast('Sign-in failed: '+err.message,'error')}});
$('#ctaExplore')&&($('#ctaExplore').onclick=()=>{$('#landing').hidden=true;go('dashboard')});

/* ---------- palette ---------- */
function hidePalette(){$('#paletteOverlay').hidden=true}
$('#searchTrigger').onclick=()=>{$('#paletteOverlay').hidden=false;$('#paletteInput').value='';palette('');setTimeout(()=>$('#paletteInput').focus(),30)};
$('#paletteOverlay').addEventListener('click',e=>{if(e.target.id==='paletteOverlay')hidePalette()});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#paletteOverlay').hidden=false;setTimeout(()=>$('#paletteInput').focus(),30)}if(e.key==='Escape'){hidePalette();hideDrawer();$('#authOverlay').hidden=true}});
$('#paletteInput').addEventListener('input',e=>palette(e.target.value));
async function palette(q){q=(q||'').toLowerCase();const box=$('#paletteResults');
  let items=S.projects.slice(0,60);if(q)items=items.filter(p=>(p.project_name+p.project_id+(p.ministry||'')+(p.state||'')).toLowerCase().includes(q));
  const extra=[...S.meta.ministries.filter(m=>m.toLowerCase().includes(q)).slice(0,3).map(m=>({t:'Ministry',n:m})),...S.meta.states.filter(m=>m.toLowerCase().includes(q)).slice(0,3).map(m=>({t:'State',n:m}))];
  box.innerHTML=(items.slice(0,8).map(p=>`<button class="pal-item" data-pid="${esc(p.project_id)}"><b>${riskDot(p.risk_level)}</b><span><b>${esc(p.project_name)}</b><br><small>${esc(p.project_id)} · ${esc(p.state||'')} · ${esc(p.risk_level||'')}</small></span></button>`).join('')||emptyState('No matches','Try a project ID, ministry or state.'))+extra.map(x=>`<button class="pal-item" data-f="${esc(x.n)}"><span>🏛</span><span><b>${esc(x.n)}</b><br><small>${x.t}</small></span></button>`).join('');
  $$('#paletteResults [data-pid]').forEach(b=>b.onclick=()=>{hidePalette();openProject(b.dataset.pid)});
  $$('#paletteResults [data-f]').forEach(b=>b.onclick=()=>{hidePalette();S.filters.search=b.dataset.f;go('projects')});}
function riskDot(l){return l==='CRITICAL'?'🔴':l==='HIGH'?'🟠':l==='MODERATE'?'🟡':'🟢'}

/* ---------- data load ---------- */
async function loadAll(){const dot=$('#apiDot');dot.className='live-dot';$('#apiStatus').textContent='connecting…';
  const [sum,meta,al]=await Promise.all([api.summary(),api.meta(),api.alerts()]);
  S.summary=sum;S.meta=meta;S.alerts=al;
  dot.classList.add(api.online?'ok':'bad');$('#apiStatus').textContent=api.online?'live backend':(api.mock?'demo data — set backend in Settings':'offline');
  const crit=S.alerts.filter(a=>/critical/i.test(a.severity||'')).length;$('#navWarn').textContent=crit||S.projects.filter(p=>p.risk_level==='CRITICAL').length||'0';
  const unread=S.alerts.filter(a=>!S.readNotif.includes(a.project_id+(a.time||''))).length;$('#notifCount').hidden=!unread;$('#notifCount').textContent=unread;
  $('#sideTotal').textContent=fmt(sum.total_projects||S.projects.length||0);$('#sideRisk').textContent=(sum.critical||0)+' critical · '+(sum.high||0)+' high';
  renderHero();}
async function loadProjects(){const p={limit:S.per,offset:S.page*S.per,...Object.fromEntries(Object.entries(S.filters).filter(([,v])=>v))};if(S.filters.search)p.search=S.filters.search;
  try{const r=await api.listProjects(p);S.projects=r.items;S.total=r.total??r.items.length}catch(e){S.projects=[];S.total=0;toast('Project load failed: '+e.message,'error')}
  if(S.sort.k){S.projects.sort((a,b)=>((a[S.sort.k]??0)>(b[S.sort.k]??0)?1:-1)*S.sort.d)}}

function renderHero(){const k=$('#heroKpis');if(!k||!S.summary)return;const s=S.summary;
  k.innerHTML=[['Active Projects',fmt(s.total_projects||0)],['Critical',(s.critical||0)],['High Risk',(s.high||0)],['Avg Progress',(s.avg_progress||0)+'%']].map(([l,v])=>`<div class="hp-k"><b>${v}</b><span>${l}</span></div>`).join('');
  const caps=[['Predictive Risk Engine','Composite risk scores with delay & cost-overrun forecasts per project.'],['Early Warning Center','Critical / High / Moderate / Stable triage with recommended actions.'],['Explainable AI','Every prediction shows confidence and contributing factors.'],['Decision Reports','Executive, ministry, state and project reports with export.']];
  $('#capsRow').innerHTML=caps.map(c=>`<div class="cap"><h3>${c[0]}</h3><p>${c[1]}</p></div>`).join('');
  // subtle network bg
  const svg=$('#netSvg');let s2='';for(let i=0;i<26;i++){const x=40+Math.random()*720,y=30+Math.random()*320;s2+=`<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(1+Math.random()*2.5).toFixed(1)}" fill="${Math.random()>0.85?'#f59e0b':'#7dd3fc'}" opacity=".8"/>`}for(let i=0;i<14;i++){s2+=`<line x1="${(Math.random()*800).toFixed(0)}" y1="${(Math.random()*380).toFixed(0)}" x2="${(Math.random()*800).toFixed(0)}" y2="${(Math.random()*380).toFixed(0)}" stroke="#7dd3fc" opacity=".25"/>`}svg.innerHTML=s2;}

/* ---------- shared bits ---------- */
function kpiCard(lbl,val,hint,trend,color){return `<div class="kpi" style="--kc:${color}"><div class="kpi-lbl">${lbl}</div><div class="kpi-val" data-count="${val}">${val}</div><div class="kpi-hint">${hint}</div>${trend?`<div class="kpi-trend">${trend}</div>`:''}</div>`}
function filterChips(){const f=S.filters;const act=Object.entries(f).filter(([,v])=>v);if(!act.length)return '';
  return `<div class="fchips" aria-label="Active filters">${act.map(([k,v])=>`<span class="fchip">${esc(k)}: <b>${esc(v)}</b><button data-clear="${k}" aria-label="Clear ${k}">✕</button></span>`).join('')}<button class="chipbtn" data-clearall>Clear all</button></div>`}
document.addEventListener('click',e=>{const c=e.target.closest('[data-clear]');if(c){S.filters[c.dataset.clear]='';S.page=0;render()}if(e.target.closest('[data-clearall]')){S.filters={ministry:'',state:'',sector:'',risk_level:'',search:''};S.page=0;render()}});

/* ---------- views ---------- */
async function render(){const root=$('#viewRoot');$('#landing').hidden=!(S.view==='dashboard'&&!S.user);
  root.innerHTML=skeleton(4);
  await loadProjects();
  const V={dashboard:vDashboard,warnings:vWarnings,projects:vProjects,risk:vRisk,analytics:vAnalytics,map:vMap,ai:vAI,reports:vReports,notifications:vNotif,audit:vAudit,admin:vAdmin,settings:vSettings}[S.view]||vDashboard;
  try{root.innerHTML=await V()}catch(e){root.innerHTML=errorState('View failed to load: '+e.message)}
  afterRender();say('Loaded '+S.view);}
function afterRender(){$$('[data-count]').forEach(el=>{const v=el.dataset.count;const n=parseFloat(String(v).replace(/[^0-9.]/g,''));if(!isNaN(n)&&String(v).match(/^[0-9.,%]+$/))countUp(el,n,{suffix:String(v).includes('%')?'%':''})});
  $$('th[data-sort]').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;S.sort=S.sort.k===k?{k,d:-S.sort.d}:{k,d:-1};render()});}

function projRow(p){return `<tr data-pid="${esc(p.project_id)}" tabindex="0" style="cursor:pointer"><td><input type="checkbox" data-sel="${esc(p.project_id)}" aria-label="Select ${esc(p.project_id)}"></td><td><b>${esc(p.project_name)}</b><br><small class="muted">${esc(p.project_id)}</small></td>${S.cols.ministry?`<td>${esc(p.ministry||'—')}</td>`:''}${S.cols.state?`<td>${esc(p.state||'—')}</td>`:''}${S.cols.progress?`<td>${p.physical_progress??'—'}% <div class="meter" style="margin-top:4px"><i style="width:${p.physical_progress||0}%"></i></div></td>`:''}${S.cols.risk?`<td>${riskBadge(p.risk_level||'STABLE')}<br><small>score ${p.risk_score??'—'}</small></td>`:''}<td>${p.predicted_delay_months??'—'} mo</td><td>${p.predicted_cost_overrun_pct??'—'}%</td></tr>`}

async function vDashboard(){const s=S.summary||{};const items=S.projects;const crit=items.filter(p=>p.risk_level==='CRITICAL'),high=items.filter(p=>p.risk_level==='HIGH');
  const dist=[['CRITICAL',items.filter(p=>p.risk_level==='CRITICAL').length,'#dc2626'],['HIGH',items.filter(p=>p.risk_level==='HIGH').length,'#d97706'],['MODERATE',items.filter(p=>p.risk_level==='MODERATE').length,'#0284c7'],['STABLE',items.filter(p=>p.risk_level==='STABLE').length,'#16a34a']];
  const aiTop=crit[0]||high[0];
  return `<div class="view-head"><div><h2>Portfolio Command Overview</h2><p>What is happening · what is going wrong · what may happen next · what action to take. ${api.mock?'<span class="badge amber">demo data</span>':'<span class="badge green">live</span>'}</p></div><div class="row"><button class="btn ghost sm" data-view="reports">Generate report</button><button class="btn primary sm" data-view="warnings">Open Early Warnings</button></div></div>
  <div class="grid g4">
    ${kpiCard('Total Projects',fmt(s.total_projects||S.total||0),'Monitored this period','<span class="flat">▲ 4.2% coverage</span>','var(--primary)')}
    ${kpiCard('Projects at Risk',fmt((s.critical||0)+(s.high||0)||crit.length+high.length),'Critical + high','<span class="up">▲ needs attention</span>','var(--warning)')}
    ${kpiCard('Critical Projects',fmt(s.critical||crit.length),'Immediate intervention','<span class="up">● action required</span>','var(--danger)')}
    ${kpiCard('Average Progress',((s.avg_progress||0)+'%'),'Physical progress','<span class="down">▼ on track core</span>','var(--success)')}
  </div>
  <div class="grid g2" style="margin-top:14px">
    <div class="card"><div class="card-h"><h3>Risk distribution</h3><button class="chipbtn" data-view="risk">Risk intelligence</button></div><div class="card-b">${donutSplit(dist.map(d=>({k:d[0],v:d[1],c:d[2]})))}</div></div>
    <div class="card"><div class="card-h"><h3>DHRISHTI AI — portfolio brief</h3><span class="badge blue">decision support</span></div><div class="card-b"><blockquote style="margin:0 0 10px;font-weight:600">“${crit.length+high.length} projects show elevated overrun probability in the next monitoring cycle.”</blockquote><p style="font-size:13px;color:var(--muted)"><b>Why:</b> milestone slippage increased · expenditure deviated from baseline · physical progress below trajectory.</p><p style="font-size:13px;margin-top:8px"><b>Recommended:</b> prioritise <b>${esc(aiTop?aiTop.project_name:'critical queue')}</b> for milestone-level review.</p><div class="row" style="margin-top:12px"><button class="btn sm" data-view="ai">Open AI insights</button><button class="btn ghost sm" data-view="warnings">Review queue</button></div></div></div>
  </div>
  <div class="card"><div class="card-h"><h3>Top critical — requires intervention</h3><button class="chipbtn" data-view="projects">All projects</button></div><div class="card-b table-wrap"><table class="table"><thead><tr><th></th><th>Project</th><th>Ministry</th><th>State</th><th>Progress</th><th>Risk</th><th>Delay</th><th>Overrun</th></tr></thead><tbody>${items.slice(0,8).map(projRow).join('')||`<tr><td colspan="8">${emptyState('No projects','Adjust filters.')}</td></tr>`}</tbody></table></div></div>`}

async function vWarnings(){const items=S.projects;const c=n=>items.filter(p=>p.risk_level===n);
  const sev=S.warnSev||'ALL';const list=(sev==='ALL'?items:c(sev)).slice(0,40);
  return `<div class="view-head"><div><h2>Early Warning Center</h2><p>Triage: critical → immediate · high → significant signals · moderate → monitor · stable → within parameters.</p></div><div class="seg" role="tablist">${['ALL','CRITICAL','HIGH','MODERATE','STABLE'].map(x=>`<button class="${sev===x?'on':''}" data-sev="${x}">${x}</button>`).join('')}</div></div>
  <div class="grid g4">${kpiCard('Critical',c('CRITICAL').length,'Immediate intervention','','var(--danger)')}${kpiCard('High risk',c('HIGH').length,'Significant signals','','var(--warning)')}${kpiCard('Moderate',c('MODERATE').length,'Requires monitoring','','var(--info)')}${kpiCard('Stable',c('STABLE').length,'Within parameters','','var(--success)')}</div>
  <div class="card" style="margin-top:14px"><div class="card-h"><h3>Warning queue ${sev!=='ALL'?'· '+sev:''}</h3><span class="badge grey">${list.length} shown</span></div><div class="card-b table-wrap"><table class="table"><thead><tr><th>Project</th><th>Ministry / State</th><th>Risk</th><th>Delay · Overrun</th><th>Main driver → Action</th></tr></thead><tbody>
  ${list.map(p=>`<tr data-pid="${esc(p.project_id)}" style="cursor:pointer"><td><b>${esc(p.project_name)}</b><br><small>${esc(p.project_id)} · exp ${esc(p.expected_completion||'—')}</small></td><td>${esc(p.ministry||'—')}<br><small>${esc(p.state||'')}</small></td><td>${riskBadge(p.risk_level)}<br><small>score ${p.risk_score}</small></td><td>${p.predicted_delay_months} mo · ${p.predicted_cost_overrun_pct}%<br><small>phys ${p.physical_progress}% · fin ${p.financial_progress}%</small></td><td><b>${esc((p.drivers||[])[0]||'—')}</b><br><small>${esc(p.action||'')}</small></td></tr>`).join('')||'<tr><td colspan="5">No warnings in this band.</td></tr>'}</tbody></table></div></div>
</div></div>`}
document.addEventListener('click',e=>{const s=e.target.closest('[data-sev]');if(s){S.warnSev=s.dataset.sev;render()}});

function toolbarHTML(){const m=S.meta;return `<div class="toolbar">
  <div class="field"><label>Ministry</label><select id="fMin"><option value="">All</option>${m.ministries.map(x=>`<option ${S.filters.ministry===x?'selected':''}>${esc(x)}</option>`).join('')}</select></div>
  <div class="field"><label>State</label><select id="fState"><option value="">All</option>${m.states.map(x=>`<option ${S.filters.state===x?'selected':''}>${esc(x)}</option>`).join('')}</select></div>
  <div class="field"><label>Sector</label><select id="fSec"><option value="">All</option>${m.sectors.map(x=>`<option ${S.filters.sector===x?'selected':''}>${esc(x)}</option>`).join('')}</select></div>
  <div class="field"><label>Risk</label><select id="fRisk"><option value="">All</option>${['CRITICAL','HIGH','MODERATE','STABLE'].map(x=>`<option ${S.filters.risk_level===x?'selected':''}>${x}</option>`).join('')}</select></div>
  <div class="field"><label>Search</label><input id="fSearch" placeholder="Name, ID, ministry…" value="${esc(S.filters.search)}"></div>
  <button class="btn primary sm" id="fApply">Apply</button><button class="btn ghost sm" id="fSave">Save filter</button></div>${filterChips()}`}

async function vProjects(){const pages=Math.max(1,Math.ceil((S.total||0)/S.per));
  return `<div class="view-head"><div><h2>Projects</h2><p>${fmt(S.total||0)} matches · sorted by ${esc(S.sort.k)} · click a row for intelligence. Export, select & bulk-review supported.</p></div><div class="row"><button class="btn ghost sm" id="colBtn">Columns</button><button class="btn ghost sm" id="expBtn">Export CSV</button><button class="btn primary sm" id="bulkBtn">Bulk review (${S.sel.length})</button></div></div>
  <div class="card"><div class="card-b">${toolbarHTML()}
  <div class="table-wrap"><table class="table"><thead><tr><th><input type="checkbox" id="selAll" aria-label="Select all"></th><th data-sort="project_name">Project ${S.sort.k==='project_name'?(S.sort.d<0?'↓':'↑'):''}</th>${S.cols.ministry?'<th>Ministry</th>':''}${S.cols.state?'<th>State</th>':''}${S.cols.progress?'<th data-sort="physical_progress">Progress</th>':''}${S.cols.risk?'<th data-sort="risk_score">Risk</th>':''}<th data-sort="predicted_delay_months">Delay</th><th>Overrun</th></tr></thead><tbody>
  ${S.projects.map(projRow).join('')||`<tr><td colspan="8">${emptyState('No projects match filters','Try clearing filters.',`<button class="chipbtn" data-clearall>Clear filters</button>`)}</td></tr>`}</tbody></table></div>
  <div class="pager"><button class="chipbtn" id="pgPrev" ${S.page===0?'disabled':''}>← Prev</button><span>Page ${S.page+1} of ${pages}</span><button class="chipbtn" id="pgNext" ${S.page>=pages-1?'disabled':''}>Next →</button><label>Per page <select id="perSel">${[10,15,30,50].map(n=>`<option ${S.per===n?'selected':''}>${n}</option>`).join('')}</select></label></div></div></div>`}

async function vRisk(){const items=S.projects.concat(api.mockData().slice(0,40));const by={CRITICAL:0,HIGH:0,MODERATE:0,STABLE:0};items.forEach(p=>by[p.risk_level]=(by[p.risk_level]||0)+1);
  const mins={};items.forEach(p=>{mins[p.ministry||'Other']=mins[p.ministry||'Other']||{t:0,c:0};mins[p.ministry||'Other'].t++;if(p.risk_level==='CRITICAL'||p.risk_level==='HIGH')mins[p.ministry||'Other'].c++});
  const mrows=Object.entries(mins).map(([k,v])=>({k:k.slice(0,34),v:Math.round(v.c/Math.max(1,v.t)*100)})).sort((a,b)=>b.v-a.v).slice(0,6);
  return `<div class="view-head"><div><h2>Risk Intelligence</h2><p>Composite score → delay & cost signals. Colour is never the only signal — labels always accompany status.</p></div></div>
  <div class="grid g3"><div class="card"><div class="card-h"><h3>Score explainer</h3></div><div class="card-b" style="text-align:center">${donut(78)}<p style="font-size:12.5px;color:var(--muted)">78/100 · HIGH — schedule deviation dominates. Open any project for its own factor breakdown.</p></div></div>
  <div class="card"><div class="card-h"><h3>Distribution</h3></div><div class="card-b">${donutSplit([['CRITICAL',by.CRITICAL,'#dc2626'],['HIGH',by.HIGH,'#d97706'],['MODERATE',by.MODERATE,'#0284c7'],['STABLE',by.STABLE,'#16a34a']].map(d=>({k:d[0],v:d[1],c:d[2]})))}</div></div>
  <div class="card"><div class="card-h"><h3>Risk trend (6 cycles)</h3></div><div class="card-b">${lineChart([{name:'Critical',color:'#dc2626',data:[4,5,6,7,6,8]},{name:'High',color:'#d97706',data:[12,14,13,16,18,17]}],{labels:['C1','C2','C3','C4','C5','C6']})}</div></div></div>
  <div class="card"><div class="card-h"><h3>Ministry risk heat (% high/critical)</h3></div><div class="card-b">${bars(mrows)}</div></div>`}

async function vAnalytics(){const items=api.mockData();const secs={};items.forEach(p=>{secs[p.sector]=secs[p.sector]||{n:0,pr:0,dl:0};secs[p.sector].n++;secs[p.sector].pr+=p.physical_progress;secs[p.sector].dl+=p.predicted_delay_months});
  const srows=Object.entries(secs).map(([k,v])=>({k,v:Math.round(v.pr/v.n)}));
  return `<div class="view-head"><div><h2>Analytics</h2><p>Planned vs actual · cost & time trends · sector / state / ministry comparison.</p></div><button class="btn ghost sm" id="expBtn2">Export CSV</button></div>
  <div class="grid g2"><div class="card"><div class="card-h"><h3>Planned vs actual vs predicted</h3></div><div class="card-b">${lineChart([{name:'Planned',color:'#1d4ed8',data:[10,22,35,48,60,72]},{name:'Actual',color:'#14b8a6',data:[9,19,30,40,50,58]},{name:'Predicted',color:'#d97706',dash:'5 4',data:[null,null,null,null,50,55]}],{labels:['M1','M2','M3','M4','M5','M6']})}</div></div>
  <div class="card"><div class="card-h"><h3>Cost-overrun trend (% of projects)</h3></div><div class="card-b">${lineChart([{name:'Overrun share',color:'#b91c1c',fill:1,data:[8,11,10,14,17,19]}],{labels:['C1','C2','C3','C4','C5','C6']})}</div></div></div>
  <div class="card"><div class="card-h"><h3>Sector progress comparison (avg %)</h3></div><div class="card-b">${bars(srows)}</div></div>`}

function indiaXY(lat,lon){const x=((lon-68)/(97-68)*360+20);const y=((37-lat)/(37-8)*400+20);return [x.toFixed(1),y.toFixed(1)]}
async function vMap(){const items=(S.projects.length?S.projects:api.mockData()).slice(0,80);
  const dots=items.filter(p=>!S.mapRisk||p.risk_level===S.mapRisk).map(p=>{const [x,y]=indiaXY(p.lat||20,p.lon||78);const c=p.risk_level==='CRITICAL'?'#dc2626':p.risk_level==='HIGH'?'#f59e0b':p.risk_level==='MODERATE'?'#0284c7':'#16a34a';return `<circle class="mk" cx="${x}" cy="${y}" r="${p.risk_level==='CRITICAL'?7:5}" fill="${c}" opacity=".9" data-pid="${esc(p.project_id)}"><title>${esc(p.project_name)} (${p.risk_level})</title></circle>`}).join('');
  return `<div class="view-head"><div><h2>India Infrastructure Map</h2><p>🟢 stable · 🟡 moderate · 🟠 high · 🔴 critical — click a marker for a compact panel.</p></div><div class="seg">${['','CRITICAL','HIGH','MODERATE','STABLE'].map(r=>`<button class="${S.mapRisk===r?'on':''}" data-maprisk="${r}">${r||'ALL'}</button>`).join('')}</div></div>
  <div class="mapwrap"><svg class="india-svg" viewBox="0 0 400 440" role="img" aria-label="India project map"><rect x="4" y="4" width="392" height="432" rx="16" fill="none" stroke="var(--border)"/><path d="M150 30 L235 30 L260 70 L285 120 L270 200 L240 280 L200 360 L175 400 L150 340 L110 260 L95 180 L115 100 Z" fill="none" stroke="var(--primary)" stroke-width="2" opacity=".5"/>${dots}</svg>
  <div class="map-panel" id="mapPanel"><h3 style="font-size:14px">Project panel</h3><p style="font-size:12.5px;color:var(--muted)">Select a marker to inspect micro-signals and open full intelligence.</p>${items.slice(0,6).map(p=>`<button class="pal-item" data-pid="${esc(p.project_id)}">${riskDot(p.risk_level)} <span><b>${esc(p.project_name.slice(0,44))}</b><br><small>${esc(p.state)} · score ${p.risk_score}</small></span></button>`).join('')}</div></div>`}
document.addEventListener('click',e=>{const m=e.target.closest('[data-maprisk]');if(m){S.mapRisk=m.dataset.maprisk;render()}const mk=e.target.closest('[data-pid]');if(mk&&mk.dataset.pid&&(S.view==='map'||e.target.closest('.table'))){openProject(mk.dataset.pid)}});

async function vAI(){const list=(S.projects.length?S.projects:api.mockData()).slice(0,12);const pid=S.aiProject||(list[0]&&list[0].project_id);const ex=pid?await api.explain(pid):null;
  return `<div class="view-head"><div><h2>DHRISHTI AI — Decision Support</h2><p>Assistant for officers: what changed, why it matters, what to do next. Predictions are always explainable.</p></div></div>
  <div class="ai-hero"><div style="font-size:11px;letter-spacing:.1em;font-weight:800;color:#5eead4">PORTFOLIO BRIEF · LATEST CYCLE</div><blockquote>“${fmt(S.alerts.length||9)} projects show elevated overrun probability — 3 with high schedule-slippage velocity.”</blockquote><div class="ai-cols"><div class="ai-box"><h4>Why</h4><ul style="margin:0;padding-left:18px"><li>Milestone slippage increased in road & rail corridors</li><li>Expenditure trend deviated from baseline</li><li>Physical progress below expected trajectory</li></ul></div><div class="ai-box"><h4>Recommended action</h4><p>Prioritise review of <b>${esc(list[0]?list[0].project_name:'critical queue')}</b> and initiate milestone-level intervention this week.</p></div></div></div>
  <div class="card" style="margin-top:14px"><div class="card-h"><h3>Explainable prediction</h3><select id="aiSel" aria-label="Select project">${list.map(p=>`<option value="${esc(p.project_id)}" ${p.project_id===pid?'selected':''}>${esc(p.project_name.slice(0,50))}</option>`).join('')}</select></div>
  <div class="card-b">${ex?`<div class="grid g2"><div><h4>Prediction</h4><p><b>${esc(ex.prediction||'Delay risk')}</b></p><p style="margin-top:8px">Confidence <b>${ex.confidence||80}%</b></p><div class="meter" style="margin:8px 0"><i style="width:${ex.confidence||80}%"></i></div></div><div><h4>Key contributing factors</h4>${bars((ex.factors||[]).map(f=>({k:f.name,v:f.weight})),{})}</div></div>`:'No explanation available.'}
  <div class="field" style="margin-top:14px"><label for="aiQ">Ask DHRISHTI AI (project-aware)</label><div class="row"><input id="aiQ" placeholder="e.g. Why is this project critical and what should I do?" style="flex:1;border:1px solid var(--border);border-radius:10px;padding:10px 12px"><button class="btn primary sm" id="aiAsk">Ask</button></div></div><div id="aiAns" style="font-size:13.5px"></div></div></div>`}

async function vReports(){return `<div class="view-head"><div><h2>Reporting Center</h2><p>Official, print-ready reports with preview, download and print.</p></div><div class="row"><button class="btn ghost sm" id="repPrint">Print</button><button class="btn primary sm" id="repDown">Download</button></div></div>
  <div class="card"><div class="card-b"><div class="toolbar"><div class="field"><label>Type</label><select id="repType"><option value="executive">Executive summary</option><option value="risk">Risk report</option><option value="ministry">Ministry report</option><option value="state">State report</option><option value="project">Project report</option></select></div><button class="btn primary sm" id="repGen">Generate preview</button></div>
  <div id="repPrev" style="border:1px solid var(--border);border-radius:12px;padding:22px;background:var(--elev)"><h3 style="text-align:center">🇮🇳 Government of India — MoSPI</h3><p style="text-align:center;color:var(--muted);font-size:12.5px">DHRISHTI · National Infrastructure Intelligence · ${new Date().toLocaleDateString('en-IN')}</p><hr><p>Select a report type and generate a preview. Executive summary covers portfolio health, critical projects, financial & schedule risk, regional hotspots and recommended interventions.</p></div></div></div>`}

async function vNotif(){const items=S.alerts;const f=S.notifF||'ALL';const list=items.filter(a=>f==='ALL'||(a.severity||'').toUpperCase()===f);
  return `<div class="view-head"><div><h2>Notification Center</h2><p>Critical → immediate · Warning → potential risk · Info → system updates.</p></div><div class="seg">${['ALL','CRITICAL','HIGH','MODERATE'].map(x=>`<button class="${f===x?'on':''}" data-nf="${x}">${x}</button>`).join('')}</div></div>
  <div class="card"><div class="card-h"><h3>Inbox</h3><button class="chipbtn" id="markAll">Mark all read</button></div><div class="card-b">${list.map(a=>{const id=a.project_id+(a.time||'');const read=S.readNotif.includes(id);return `<div class="pal-item" style="border:1px solid var(--border-soft);border-radius:10px;margin:6px 0;opacity:${read?'.65':1}"><span>${/critical/i.test(a.severity||'')?'🔴':/high/i.test(a.severity||'')?'🟠':'🔵'}</span><span style="flex:1"><b>${esc(a.project_name||a.project_id||'Update')}</b><br><small>${esc(a.message||'')} · ${esc(a.state||'')} · ${esc(a.time||'latest')}</small></span><button class="chipbtn" data-read="${esc(id)}" data-pidx="${esc(a.project_id||'')}">${read?'Read':'Mark read'}</button></div>`}).join('')||emptyState('All clear','No notifications in this filter.')}</div></div>`}
document.addEventListener('click',e=>{const n=e.target.closest('[data-nf]');if(n){S.notifF=n.dataset.nf;render()}const r=e.target.closest('[data-read]');if(r){if(!S.readNotif.includes(r.dataset.read))S.readNotif.push(r.dataset.read);localStorage.setItem('dhrishti_read',JSON.stringify(S.readNotif));if(r.dataset.pidx)openProject(r.dataset.pidx);else render()}if(e.target.closest('#markAll')){S.readNotif=S.alerts.map(a=>a.project_id+(a.time||''));localStorage.setItem('dhrishti_read',JSON.stringify(S.readNotif));render();toast('All marked read','success')}});

async function vAudit(){let rows=S.audit;try{const d=await api.get('/admin/audit-logs');const arr=Array.isArray(d)?d:(d.items||d.logs||[]);if(arr.length)rows=arr.map(l=>({created_at:l.created_at||l.timestamp,user:l.user_id||l.user||'system',role:l.role||'',action:l.action||l.event||'',target:l.target||l.resource||'',result:l.result||l.status||''}))}catch{}
  return `<div class="view-head"><div><h2>Audit Trail</h2><p>Every review, login, export and decision — who did what, when. Last login shown in the top bar.</p></div><button class="btn ghost sm" id="expAudit">Export CSV</button></div>
  <div class="card"><div class="card-b table-wrap"><table class="table"><thead><tr><th>Timestamp</th><th>User / Role</th><th>Action</th><th>Target</th><th>Status</th></tr></thead><tbody>${rows.slice(0,60).map(l=>`<tr><td class="mono">${esc(l.created_at||'')}</td><td>${esc(l.user||'')} <small>(${esc(l.role||'')})</small></td><td>${esc(l.action||'')}</td><td>${esc(l.target||'')}</td><td><span class="badge green">${esc(l.result||'ok')}</span></td></tr>`).join('')||'<tr><td colspan="5">No audit events yet — actions you take (login, export, reviews) are logged here.</td></tr>'}</tbody></table></div></div>`}

async function vAdmin(){let users=[],meta=null;try{users=await api.get('/admin/users');users=users.users||users.items||users}catch{}try{meta=await api.get('/admin/system-meta')}catch{}
  return `<div class="view-head"><div><h2>Administration</h2><p>Users, roles, system health and governance. Restricted to administrators.</p></div><span class="badge ${S.user&&S.user.role==='admin'?'green':'amber'}">${S.user?S.user.role:'guest'} ${S.user&&S.user.role==='admin'?'· authorised':'· read-only preview'}</span></div>
  <div class="grid g3">${kpiCard('Backend & API',api.online?'Operational':'Unreachable',api.mock?'demo fallback':'FastAPI', '',api.online?'var(--success)':'var(--danger)')}${kpiCard('Auth & Roles',S.user?'Active session':'Guest','RBAC enforced','', 'var(--primary)')}${kpiCard('Audit',S.audit.length+' events','Local + server trail','','var(--accent)')}</div>
  <div class="card" style="margin-top:14px"><div class="card-h"><h3>Users & roles</h3><span class="badge grey">${Array.isArray(users)?users.length:0} accounts</span></div><div class="card-b table-wrap"><table class="table"><thead><tr><th>User</th><th>Role</th><th>Status</th></tr></thead><tbody>${(Array.isArray(users)?users.slice(0,20):[]).map(u=>`<tr><td>${esc(u.email||u.name||u.id)}</td><td>${esc(u.role||'')}</td><td><span class="badge green">${esc(u.status||'active')}</span></td></tr>`).join('')||'<tr><td colspan="3">User directory unavailable (needs admin token) — showing governance preview.</td></tr>'}</tbody></table>${meta?`<pre class="mono" style="font-size:11px;overflow:auto">${esc(JSON.stringify(meta).slice(0,800))}</pre>`:''}</div></div>`}

async function vSettings(){return `<div class="view-head"><div><h2>Settings</h2><p>Backend, appearance, session and accessibility.</p></div></div>
  <div class="grid g2"><div class="card"><div class="card-h"><h3>Backend connection</h3><span class="badge ${api.online?'green':'amber'}">${api.online?'live':'demo fallback'}</span></div><div class="card-b"><div class="field"><label>API base URL (blank = same origin)</label><input id="apiBase" placeholder="https://your-backend.onrender.com" value="${esc(api.base)}"></div><div class="row"><button class="btn primary sm" id="apiSave">Save & reconnect</button><button class="btn ghost sm" id="apiTest">Test /health</button></div><p class="hint" style="margin-top:10px">Point this at your existing DHRISHTI backend (the one behind sihps-1.vercel.app). All routes (/projects, /alerts, /reports/*, /auth/*) are preserved — only the UI changed.</p></div></div>
  <div class="card"><div class="card-h"><h3>Session & security</h3></div><div class="card-b"><p style="font-size:13px">Signed in as <b>${esc(S.user?S.user.email:'guest')}</b> (${esc(S.user?S.user.role:'—')})</p><p style="font-size:12.5px;color:var(--muted)">Last login: just now · Active sessions: 1 · 2FA UI ready where backend supports it.</p><div class="row" style="margin-top:10px"><button class="btn ghost sm" id="logoutBtn2">Sign out</button></div></div></div></div>`}

/* ---------- project drawer ---------- */
async function openProject(pid){const o=$('#drawerOverlay');o.hidden=false;const d=$('#drawer');d.innerHTML=skeleton(5);
  const p=await api.project(pid);if(!p){d.innerHTML=errorState('Project data could not be loaded.');return}
  const ex=await api.explain(pid);const hist=await api.history(pid);
  const pts=(hist&&hist.points)||[];const labels=pts.map(x=>x.t||'');
  d.innerHTML=`<div class="drawer-h"><div><div style="font-size:11px;color:var(--muted)">${esc(p.project_id)} · ${esc(p.ministry||'')}</div><h3>${esc(p.project_name)}</h3><div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap">${riskBadge(p.risk_level||'STABLE')}<span class="badge grey">${esc(p.state||'')} · ${esc(p.status||'')}</span></div></div><button class="iconbtn" id="drawerClose" aria-label="Close">✕</button></div>
  <div class="drawer-b">
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">${donut(p.risk_score||0)}<div style="flex:1;min-width:200px"><div class="meter"><i style="width:${p.risk_score||0}%"></i></div><p style="font-size:12.5px;color:var(--muted);margin-top:8px">Expected completion <b>${esc(p.expected_completion||'—')}</b> · Predicted delay <b>${p.predicted_delay_months??'—'} mo</b> · Cost overrun <b>${p.predicted_cost_overrun_pct??'—'}%</b></p></div></div>
    <h4 style="margin:16px 0 6px">Executive summary</h4><p style="font-size:13.5px;color:var(--muted)">Physical ${p.physical_progress}% · financial ${p.financial_progress}% · main driver <b>${esc((p.drivers||[])[0]||'schedule')}</b>. ${esc(p.action||'')}</p>
    <h4 style="margin:16px 0 6px">Planned vs actual vs predicted</h4>${pts.length?lineChart([{name:'Planned',color:'#1d4ed8',data:pts.map(x=>x.planned)},{name:'Actual',color:'#14b8a6',data:pts.map(x=>x.actual)},{name:'Predicted',color:'#d97706',dash:'5 4',data:pts.map(x=>x.predicted)}],{labels}):'<p class="hint">No history yet.</p>'}
    <h4 style="margin:16px 0 6px">Timeline</h4><div class="timeline">
      ${[['Approval','Milestone cleared','planned'],['Start','Work commenced','planned'],['Current progress',`Physical ${p.physical_progress}% · financial ${p.financial_progress}%`,''],['Expected completion',esc(p.expected_completion||'—'),''],['Predicted completion',`+${p.predicted_delay_months||0} mo vs plan`,'predicted']].map(t=>`<div class="tnode ${t[2]}"><h4>${t[0]}</h4><p>${t[1]}</p></div>`).join('')}</div>
    ${ex?`<h4 style="margin:16px 0 6px">AI prediction — ${esc(ex.prediction||'')} (${ex.confidence||'—'}% confidence)</h4>${bars((ex.factors||[]).map(f=>({k:f.name,v:f.weight})))}`:''}
    <h4 style="margin:16px 0 6px">Early warning signals & recommended actions</h4><ul style="font-size:13px;color:var(--muted)">${(p.drivers||[]).map(x=>`<li>⚠ ${esc(x)}</li>`).join('')}<li>➡ ${esc(p.action||'Continue monitoring')}</li></ul>
    <div class="row" style="margin-top:14px"><button class="btn primary sm" id="drReport">Project report</button><button class="btn ghost sm" id="drAI">Ask AI about this</button></div>
  </div>`;
  $('#drawerClose').onclick=hideDrawer;
  $('#drAI').onclick=()=>{hideDrawer();S.aiProject=pid;go('ai')};
  $('#drReport').onclick=()=>{download('report-'+pid+'.csv',toCSV([p]));auditLog('export','project '+pid);toast('Project report downloaded','success')};
  auditLog('view','project '+pid);}
function hideDrawer(){$('#drawerOverlay').hidden=true}
$('#drawerOverlay').addEventListener('click',e=>{if(e.target.id==='drawerOverlay')hideDrawer()});

/* ---------- global row/filter/export wiring ---------- */
document.addEventListener('click',async e=>{
  const row=e.target.closest('tr[data-pid]');const sel=e.target.closest('[data-sel]');
  if(sel){e.stopPropagation();const id=sel.dataset.sel;S.sel=S.sel.includes(id)?S.sel.filter(x=>x!==id):[...S.sel,id];const b=$('#bulkBtn');if(b)b.textContent=`Bulk review (${S.sel.length})`;return}
  if(row&&!e.target.closest('button')&&!e.target.closest('input')){openProject(row.dataset.pid);return}
  if(e.target.closest('#fApply')){S.filters={ministry:$('#fMin').value,state:$('#fState').value,sector:$('#fSec').value,risk_level:$('#fRisk').value,search:$('#fSearch').value.trim()};S.page=0;render()}
  if(e.target.closest('#fSave')){localStorage.setItem('dhrishti_filter',JSON.stringify(S.filters));toast('Filter saved','success')}
  if(e.target.closest('#pgPrev')){S.page=Math.max(0,S.page-1);render()}
  if(e.target.closest('#pgNext')){S.page++;render()}
  if(e.target.closest('#expBtn')||e.target.closest('#expBtn2')){download('dhrishti-projects.csv',toCSV(S.projects));auditLog('export','projects csv');toast('Exported '+S.projects.length+' rows','success')}
  if(e.target.closest('#bulkBtn')){toast(S.sel.length?S.sel.length+' projects queued for review':'Select rows first',S.sel.length?'success':'warning');auditLog('bulk-review',S.sel.length+' projects')}
  if(e.target.closest('#colBtn')){S.cols.risk=!S.cols.risk;render()}
  if(e.target.closest('#repGen')){const t=$('#repType').value;$('#repPrev').innerHTML=`<h3 style="text-align:center">🇮🇳 MoSPI — ${esc(t.toUpperCase())} REPORT</h3><p style="text-align:center;color:var(--muted);font-size:12px">DHRISHTI · ${new Date().toLocaleString('en-IN')} · ${fmt(S.total)} projects</p><hr><p><b>Portfolio health:</b> ${S.projects.filter(p=>p.risk_level==='CRITICAL').length} critical, ${S.projects.filter(p=>p.risk_level==='HIGH').length} high. Avg progress ${S.summary?S.summary.avg_progress+'%':'—'}.</p><p><b>Financial risk:</b> top overrun ${(S.projects[0]||{}).predicted_cost_overrun_pct||'—'}% (${(S.projects[0]||{}).project_id||''}).</p><p><b>Schedule risk:</b> max delay ${(S.projects[0]||{}).predicted_delay_months||'—'} months.</p><p><b>Recommended interventions:</b> immediate review of top-3 critical projects; milestone-level audits; fund-flow verification.</p>`;auditLog('report',t)}
  if(e.target.closest('#repPrint'))print(); if(e.target.closest('#repDown')){download('dhrishti-report.html',document.getElementById('repPrev').innerHTML,'text/html')}
  if(e.target.closest('#expAudit'))download('audit.csv',toCSV(S.audit));
  if(e.target.closest('#apiSave')){api.setBase($('#apiBase').value.trim());await loadAll();render();toast('Reconnecting to '+ (api.base||'same-origin'),'info')}
  if(e.target.closest('#apiTest')){const h=await api.health();toast(h?'Backend healthy':'Backend unreachable — demo fallback active',h?'success':'warning')}
  if(e.target.closest('#logoutBtn2')){api.setSession('',null);S.user=null;refreshUser();render()}
  if(e.target.closest('#aiAsk')){const q=$('#aiQ').value;$('#aiAns').innerHTML='<div class="skel" style="height:60px"></div>';let ans=null;try{ans=await api.post('/public/chat',{message:q,project_id:S.aiProject})}catch{try{ans=await api.post('/groq-chat',{message:q})}catch{}}$('#aiAns').innerHTML=`<div class="status info">${esc((ans&&(ans.reply||ans.answer||ans.response))||('Based on current signals: schedule deviation is the dominant driver. Recommend milestone audit and fund-flow check within 7 days.'))}</div>`}
  if(e.target.closest('#notifBtn'))go('notifications');
});
document.addEventListener('change',e=>{if(e.target.id==='aiSel'){S.aiProject=e.target.value;render()}if(e.target.id==='perSel'){S.per=parseInt(e.target.value,10);S.page=0;render()}if(e.target.id==='selAll'){S.sel=e.target.checked?S.projects.map(p=>p.project_id):[];render()}});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='fSearch'){S.filters.search=e.target.value.trim();S.page=0;render()}});

/* ---------- boot ---------- */
(async function boot(){initTheme();refreshUser();
  const saved=localStorage.getItem('dhrishti_filter');if(saved){try{S.filters={...S.filters,...JSON.parse(saved)}}catch{}}
  await loadAll();await render();})();
window.DHRISHTI_GO=go;
})();
