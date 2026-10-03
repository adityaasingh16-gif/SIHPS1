/* DHRISHTI API client — live backend with realistic mock fallback */
(function(){
  const LS_BASE='dhrishti_api_base', LS_TOK='dhrishti_token', LS_USER='dhrishti_user';
  const store={get:(k,d)=>{try{const v=localStorage.getItem(k);return v??d}catch{return d}},set:(k,v)=>{try{localStorage.setItem(k,v)}catch{}},del:k=>{try{localStorage.removeItem(k)}catch{}}};

  function defaultBase(){
    const q=new URLSearchParams(location.search).get('api');
    if(q) return q.replace(/\/$/,'');
    const saved=store.get(LS_BASE,'');
    if(saved) return saved;
    return ''; // same-origin (works when served by backend or Vercel rewrite)
  }
  const api={base:defaultBase(), online:false, mock:false,
    token:store.get(LS_TOK,''), user:JSON.parse(store.get(LS_USER,'null')||'null'),
    setBase(b){this.base=(b||'').replace(/\/$/,'');store.set(LS_BASE,this.base)},
    setSession(tok,user){this.token=tok||'';this.user=user||null;tok?store.set(LS_TOK,tok):store.del(LS_TOK);user?store.set(LS_USER,JSON.stringify(user)):store.del(LS_USER)},
  };

  async function req(path,opts={}){
    const url=(api.base||'')+path;
    const h={'Content-Type':'application/json',...(opts.headers||{})};
    if(api.token) h['Authorization']='Bearer '+api.token;
    const ctl=new AbortController(); const to=setTimeout(()=>ctl.abort(),15000);
    try{
      const r=await fetch(url,{...opts,headers:h,signal:ctl.signal});
      clearTimeout(to);
      const total=r.headers.get('X-Total-Count');
      let data=null; try{data=await r.json()}catch{data=null}
      if(!r.ok){const e=new Error((data&&(data.detail||data.message))||('HTTP '+r.status));e.status=r.status;e.data=data;throw e}
      return {data,total:total?parseInt(total,10):null};
    }catch(e){clearTimeout(to);throw e}
  }
  api.get=(p)=>req(p).then(r=>r.data);
  api.getFull=(p)=>req(p);
  api.post=(p,b)=>req(p,{method:'POST',body:JSON.stringify(b||{})});
  api.req=req;

  /* ---------- realistic mock dataset (used only when backend unreachable) ---------- */
  const MINISTRIES=['Ministry of Road Transport & Highways','Ministry of Railways','Ministry of Power','Ministry of Housing & Urban Affairs','Ministry of Jal Shakti','Ministry of Petroleum & Natural Gas'];
  const STATES=[['Maharashtra',19.75,75.7],['Uttar Pradesh',26.8,80.9],['Tamil Nadu',11.1,78.6],['Gujarat',22.7,71.9],['Karnataka',15.3,75.7],['Rajasthan',26.4,74.6],['Madhya Pradesh',22.9,79.5],['Bihar',25.8,85.6],['West Bengal',22.9,87.8],['Odisha',20.9,85.4],['Telangana',18.1,79.0],['Andhra Pradesh',15.9,79.7]];
  const SECTORS=['Roads & Highways','Railways','Power','Urban Housing','Water & Irrigation','Oil & Gas'];
  const RISKS=['STABLE','MODERATE','HIGH','CRITICAL'];
  function rnd(seed){let s=seed;return()=>{s=(s*9301+49297)%233280;return s/233280}}
  function mockProjects(n=120){
    const R=rnd(26103); const out=[];
    for(let i=0;i<n;i++){
      const m=MINISTRIES[Math.floor(R()*MINISTRIES.length)];
      const st=STATES[Math.floor(R()*STATES.length)];
      const risk=R(); const level=risk>0.9?'CRITICAL':risk>0.72?'HIGH':risk>0.45?'MODERATE':'STABLE';
      const prog=Math.round(20+R()*75), fin=Math.max(5,Math.min(98,prog+Math.round((R()-0.5)*22)));
      const delay=level==='CRITICAL'?Math.round(6+R()*18):level==='HIGH'?Math.round(2+R()*7):level==='MODERATE'?Math.round(R()*3):0;
      const over=level==='STABLE'?+(R()*3).toFixed(1):+(R()*(level==='CRITICAL'?38:18)).toFixed(1);
      out.push({project_id:'P-'+(26103+i),project_name:`${SECTORS[Math.floor(R()*SECTORS.length)]} Corridor Phase ${1+Math.floor(R()*4)} — ${st[0]}`,ministry:m,state:st[0],sector:SECTORS[Math.floor(R()*SECTORS.length)],lat:st[1]+(R()-0.5)*3,lon:st[2]+(R()-0.5)*3,risk_score:Math.round(risk*100),risk_level:level,physical_progress:prog,financial_progress:fin,predicted_delay_months:delay,predicted_cost_overrun_pct:over,expected_completion:`202${6+Math.floor(R()*3)}-Q${1+Math.floor(R()*4)}`,status:prog>90?'Near Completion':delay>6?'Delayed':'On Track',drivers:level==='STABLE'?['Expenditure on track']:level==='MODERATE'?['Milestone slippage detected','Expenditure variance']:['Schedule deviation','Milestone slippage','Expenditure variance'],action:level==='CRITICAL'?'Immediate review & milestone-level intervention':level==='HIGH'?'Prioritise review in next monitoring cycle':level==='MODERATE'?'Enhanced monitoring':'Continue routine monitoring'});
    }
    return out.sort((a,b)=>b.risk_score-a.risk_score);
  }
  let _mock=null;
  api.mockData=()=>{_mock=_mock||mockProjects();return _mock};

  api.health=async()=>{try{const d=await api.get('/health');api.online=true;api.mock=false;return d}catch(e){api.online=false;return null}};
  api.summary=async()=>{try{const d=await api.get('/public/summary');api.online=true;api.mock=false;return d}catch{api.online=false;api.mock=true;const p=api.mockData();return{total_projects:p.length,critical:p.filter(x=>x.risk_level==='CRITICAL').length,high:p.filter(x=>x.risk_level==='HIGH').length,avg_progress:Math.round(p.reduce((a,b)=>a+b.physical_progress,0)/p.length),mock:true}}};
  api.listProjects=async(params={})=>{const q=new URLSearchParams();Object.entries(params).forEach(([k,v])=>{if(v!==''&&v!=null)q.set(k,v)});const qs=q.toString()?('?'+q.toString()):'';
    try{const r=await api.getFull('/projects'+qs);api.online=true;api.mock=false;return{items:Array.isArray(r.data)?r.data:(r.data.items||r.data.projects||[]),total:r.total??(Array.isArray(r.data)?r.data.length:null)}}
    catch{try{const r=await api.getFull('/public/projects'+qs);api.online=true;api.mock=false;return{items:Array.isArray(r.data)?r.data:(r.data.items||[]),total:r.total??null}}
    catch{api.online=false;api.mock=true;let items=api.mockData();
      if(params.ministry)items=items.filter(p=>p.ministry===params.ministry);
      if(params.state)items=items.filter(p=>p.state===params.state);
      if(params.sector)items=items.filter(p=>p.sector===params.sector);
      if(params.risk_level)items=items.filter(p=>p.risk_level===params.risk_level);
      if(params.search){const s=params.search.toLowerCase();items=items.filter(p=>(p.project_name+p.project_id+p.ministry+p.state).toLowerCase().includes(s))}
      const total=items.length;const lim=parseInt(params.limit||'50',10),off=parseInt(params.offset||'0',10);
      return{items:items.slice(off,off+lim),total,mock:true}}}};
  api.project=async(id)=>{try{return await api.get('/projects/'+encodeURIComponent(id))}catch{try{return await api.get('/public/projects/'+encodeURIComponent(id))}catch{return api.mockData().find(p=>p.project_id===id)||null}}};
  api.explain=async(id)=>{try{return await api.get('/projects/'+encodeURIComponent(id)+'/explanation')}catch{const p=await api.project(id);if(!p)return null;const s=p.risk_score/100;return{prediction:p.risk_level==='STABLE'?'On track':'High probability of delay',confidence:Math.min(96,55+Math.round(s*40)),factors:[{name:'Schedule deviation',weight:Math.round(s*42)},{name:'Milestone slippage',weight:Math.round(s*31)},{name:'Expenditure variance',weight:Math.round(s*18)},{name:'Other',weight:Math.max(4,100-Math.round(s*91))}],mock:true}}};
  api.history=async(id)=>{try{return await api.get('/projects/'+encodeURIComponent(id)+'/history')}catch{const p=await api.project(id);const base=p?p.physical_progress:50;return{points:[0,1,2,3,4,5].map(i=>({t:'M-'+(i+1),planned:Math.min(100,Math.round(base*0.6+i*8)),actual:Math.min(100,Math.round(base*0.4+i*7)),predicted:i>3?Math.min(100,Math.round(base*0.4+i*6.2)):null})),mock:true}}};
  api.alerts=async()=>{try{const d=await api.get('/alerts');return Array.isArray(d)?d:(d.items||d.alerts||[])}catch{try{const d=await api.get('/reports/alerts');return Array.isArray(d)?d:(d.items||[]) }catch{return api.mockData().filter(p=>p.risk_level==='CRITICAL'||p.risk_level==='HIGH').slice(0,12).map(p=>({severity:p.risk_level,project_id:p.project_id,project_name:p.project_name,state:p.state,ministry:p.ministry,message:`${p.risk_level==='CRITICAL'?'Immediate intervention':'Review'} required — delay ${p.predicted_delay_months} mo · overrun ${p.predicted_cost_overrun_pct}%`,time:'latest cycle',mock:true}))}}};
  api.meta=async()=>{const out={ministries:[],sectors:[],states:[]};
    try{out.ministries=(await api.get('/public/ministries')).ministries||await api.get('/public/ministries')}catch{out.ministries=MINISTRIES}
    try{const s=await api.get('/public/sectors');out.sectors=s.sectors||s}catch{out.sectors=SECTORS}
    try{const s=await api.get('/public/geo/states');out.states=(s.states||s).map?.(x=>x.name||x)||[]}catch{out.states=STATES.map(s=>s[0])}
    if(!Array.isArray(out.ministries))out.ministries=MINISTRIES; if(!Array.isArray(out.sectors))out.sectors=SECTORS; if(!out.states.length)out.states=STATES.map(s=>s[0]);
    return out};
  api.me=async()=>{if(!api.token)return api.user;try{const d=await api.get('/auth/me');api.user=d.user||d;return api.user}catch{return api.user}};
  api.login=async(email,pass)=>{try{const d=await api.post('/auth/login',{email,password:pass,username:email});const tok=d.access_token||d.token;const user=d.user||{email,role:'officer'};if(!tok)throw new Error('No token');api.setSession(tok,user);return user}catch{ // demo fallback
    const role=email.includes('admin')?'admin':email.includes('analyst')?'analyst':email.includes('agency')?'agency':'officer';
    const user={email,role,name:email.split('@')[0]};api.setSession('demo-token',user);return user}};
  window.DHRISHTI_API=api;
})();
