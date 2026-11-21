/* CivicResolve NEXUS — dependency-free accessible UI for the FastAPI service.
 * All server-provided strings are escaped before insertion into HTML.
 */
'use strict';

const state = {
  view:'overview', incidents:[], overview:null, auth:{role:'citizen',name:'Citizen',csrf:''},
  filter:{status:'all',ward:'all',category:'all',q:''},
  detail:null, focusIncident:null, chat:[{who:'bot',text:'Welcome to CivicGuide. I can explain incident priorities, help you file an issue, surface urgent reports, and walk you through citizen-verified closure.'}],
  suggestions:['Show urgent cases','How do I report an issue?','How is priority decided?'],
  reportPreview:null
};

const $=(sel,root=document)=>root.querySelector(sel);
const $$=(sel,root=document)=>[...root.querySelectorAll(sel)];
const E=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const I=(name,cls='')=>`<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const niceStatus=s=>({'in_progress':'In progress','verification':'Awaiting verification','reopened':'Reopened','assigned':'Assigned','reported':'Reported','resolved':'Verified resolved'}[s]||String(s||'').replaceAll('_',' '));
const niceTime=d=>d?new Date(d).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'—';
const clip=(s,n=95)=>String(s||'').length>n?String(s).slice(0,n).trim()+'…':String(s||'');
const badge=(v,kind='priority')=>`<span class="badge-pill ${E(String(v).toLowerCase().replaceAll(' ','_'))}">${E(kind==='status'?niceStatus(v):v)}</span>`;
const formatError=err=>typeof err==='string'?err:typeof err==='object'?JSON.stringify(err):'Unexpected error';

async function api(path,options={}){
  const res=await fetch(path,{credentials:'same-origin',...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(options.headers||{})}});
  let body;try{body=await res.json()}catch{body={detail:`HTTP ${res.status}`}}
  if(!res.ok)throw Error(Array.isArray(body.detail)?body.detail.map(e=>e.msg).join(' · '):(body.detail||`Request failed (${res.status})`));
  return body;
}
const post=(url,payload,protectedAction=false)=>api(url,{method:'POST',body:JSON.stringify(payload),headers:protectedAction?{'X-CSRF-Token':state.auth.csrf}:{}});
function toast(message,error=false){
  const node=document.createElement('div');node.className='toast'+(error?' error':'');node.textContent=message;$('#toastRegion').append(node);setTimeout(()=>node.remove(),4600);
}
function go(view){
  const allowed=['overview','explore','report','radar','verify','officer','analytics','guide'];
  state.view=allowed.includes(view)?view:'overview';
  $$('.nav-link').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));
  $('#sidebar').classList.remove('open');
  $('#breadcrumbName').textContent=({overview:'COMMAND CENTER',explore:'INCIDENT EXPLORER',report:'REPORT AN ISSUE',radar:'SIGNAL RADAR',verify:'TRUST & VERIFICATION',officer:'OFFICER WORKSPACE',analytics:'CITY INTELLIGENCE',guide:'CIVICGUIDE AI'})[state.view];
  render(); window.scrollTo({top:0,behavior:'instant'});
}
async function refresh(showLoading=false){
  try{
    if(showLoading)$('#mainContent').innerHTML=`<div class="loading"><div class="spinner"></div>Loading the latest civic signals...</div>`;
    const [items,overview,auth]=await Promise.all([api('/api/incidents'),api('/api/overview'),api('/api/auth/me')]);
    state.incidents=items;state.overview=overview;state.auth=auth;
    $('#userName').textContent=auth.role==='citizen'?'Citizen view':auth.name;
    $('.avatar').textContent=auth.role==='citizen'?'C':auth.role==='admin'?'A':'O';
    render();
  }catch(err){$('#mainContent').innerHTML=`<div class="empty-state">${I('alert')}<h3>Unable to reach the API</h3><p>${E(err.message)}</p><button class="btn secondary" id="retryBtn">Retry connection</button></div>`;$('#retryBtn')?.addEventListener('click',()=>refresh(true));}
}
function heading(eyebrow,title,description,action=''){
  return `<div class="page-heading"><div><span class="eyebrow">${E(eyebrow)}</span><h1>${E(title)}</h1><p>${E(description)}</p></div>${action}</div>`;
}
function statCard(title,value,subtitle,icon,color=''){
  return `<div class="stat-card"><div class="stat-top"><span>${E(title)}</span><span class="stat-icon ${color}">${I(icon)}</span></div><div class="number">${E(value)}</div><small>${E(subtitle)}</small></div>`;
}
function signalRow(i,n){return `<div class="signal-item ${i.priority>=78?'red':''}" data-open="${i.id}" tabindex="0" role="button" aria-label="Open ${E(i.code)}"><div class="signal-num">${String(n).padStart(2,'0')}</div><div class="signal-main"><div class="signal-title">${E(clip(i.title,95))}</div><div class="signal-meta"><span>${I('pin')} ${E(i.ward)}</span><span>${I('clock')} ${E(niceStatus(i.status))}</span></div></div><span class="signal-count">${i.report_count} ${i.report_count===1?'voice':'voices'}</span></div>`}
function bars(dict,limit=6){const arr=Object.entries(dict||{}).sort((a,b)=>b[1]-a[1]).slice(0,limit);const max=Math.max(...arr.map(x=>x[1]),1);return arr.length?arr.map(([label,num],idx)=>`<div class="chart-row"><div class="chart-label"><span>${E(label)}</span><b>${num}</b></div><progress class="progressbar" max="${max}" value="${num}" aria-label="${E(label)}: ${num}">${num}</progress></div>`).join(''):'<p class="muted">No data yet.</p>'}
function table(issues,limit=8){
  const arr=issues.slice(0,limit);
  return `<div class="table-wrap"><table><thead><tr><th>Incident</th><th>Location</th><th>Priority</th><th>Status</th><th>Signal</th><th></th></tr></thead><tbody>${arr.map(i=>`<tr><td><span class="code">${E(i.code)}</span><span class="ellipsis" title="${E(i.title)}">${E(clip(i.title,59))}</span></td><td>${E(i.ward)}<div class="muted">${E(clip(i.location,28))}</div></td><td>${badge(i.priority_label)}</td><td>${badge(i.status,'status')}</td><td>${i.report_count} ${i.report_count===1?'report':'reports'}</td><td><button class="tiny-open" data-open="${i.id}">Explore →</button></td></tr>`).join('')||'<tr><td colspan="6">No incidents to display</td></tr>'}</tbody></table></div>`;
}
function overview(){
  const stats=state.overview.stats,queue=state.overview.queue,radar=state.overview.radar;
  return `<section class="hero"><div class="hero-copy"><span class="eyebrow">✦ &nbsp; THE NEXT GENERATION OF CIVIC RESPONSE</span><h1>Better signals.<br/>Real resolution.</h1><p>Turn scattered complaints into one actionable city-wide picture. Prioritize by impact. Don't call a problem solved until people confirm it.</p><div class="hero-actions"><button class="btn primary" data-view="report">${I('plus')} Report a problem</button><button class="btn secondary" data-view="guide">${I('spark')} Ask CivicGuide</button></div></div><div class="hero-visual" aria-hidden="true"><div class="ring"></div><div class="core">${I('shield')}</div></div></section>
  <div class="stats-grid">${statCard('Active incidents',stats.active,'Awaiting resolution','layers')}${statCard('Citizen voices',stats.voices,'Community signals collected','users','blue')}${statCard('Signal clusters',stats.signal_clusters,'Connected independent reports','radio','orange')}${statCard('Verified fixes',stats.verified_fixes,'Citizens confirmed the outcome','shield','purple')}</div>
  <div class="dashboard-columns"><section class="panel"><div class="panel-heading"><div><h2>Priority response queue</h2><p>Transparent safety, context and time-based ranking</p></div><button class="text-link" data-view="officer">Open workspace →</button></div>${queue.slice(0,5).map((i,n)=>signalRow(i,n+1)).join('')||'<div class="empty-state">No active issues</div>'}</section><section class="panel"><div class="panel-heading"><div><h2>Service breakdown</h2><p>Incident distribution by department type</p></div><button class="text-link" data-view="analytics">Insights →</button></div>${bars(state.overview.categories)}</section></div>
  <div class="section-row"><h2>Explore the civic network</h2><button class="text-link" data-view="explore">Browse all incidents →</button></div><section class="panel">${table(state.incidents,5)}</section>
  <div class="trust-strip"><div class="trust-point"><span class="trust-icon">${I('radio')}</span><div><strong>Signal fusion</strong><p>Link repeated issues into shared incidents.</p></div></div><div class="trust-point"><span class="trust-icon">${I('spark')}</span><div><strong>Explainable triage</strong><p>Show why each case is prioritized.</p></div></div><div class="trust-point"><span class="trust-icon">${I('shield')}</span><div><strong>Verified outcomes</strong><p>Citizens can confirm or challenge repairs.</p></div></div><div class="trust-point"><span class="trust-icon">${I('refresh')}</span><div><strong>Feedback loop</strong><p>Disputed fixes return to the active queue.</p></div></div></div>`;
}
function filtered(){let list=state.incidents;const f=state.filter;
  if(f.status!=='all')list=list.filter(i=>i.status===f.status);
  if(f.ward!=='all')list=list.filter(i=>i.ward===f.ward);
  if(f.category!=='all')list=list.filter(i=>i.category_key===f.category);
  if(f.q)list=list.filter(i=>(i.code+' '+i.title+' '+i.ward+' '+i.location+' '+i.category).toLowerCase().includes(f.q.toLowerCase()));
  return list;
}
const wards=['RS Puram','Gandhipuram','Peelamedu','Saibaba Colony','Ukkadam','Singanallur','Saravanampatti','Town Hall','Other'];
function option(items,selected,empty='All areas'){return `<option value="all">${E(empty)}</option>`+items.map(x=>{const v=Array.isArray(x)?x[0]:x;const label=Array.isArray(x)?x[1]:x;return `<option value="${E(v)}" ${v===selected?'selected':''}>${E(label)}</option>`}).join('')}
function explore(){const f=state.filter;return `${heading('INCIDENT INTELLIGENCE','Incident Explorer','Explore open issues, corroborating reports and verified outcomes.',`<button class="btn primary" data-view="report">${I('plus')} New report</button>`)}<div class="filter-bar"><label class="field-search">${I('search')}<input id="issueSearch" aria-label="Search incidents" placeholder="Search incidents, locations, categories..." value="${E(f.q)}" /></label><select id="statusFilter" aria-label="Filter by status">${option([['reported','Reported'],['assigned','Assigned'],['in_progress','In progress'],['verification','Awaiting verification'],['reopened','Reopened'],['resolved','Verified resolved']],f.status,'All statuses')}</select><select id="wardFilter" aria-label="Filter by ward">${option(wards,f.ward,'All wards')}</select><select id="categoryFilter" aria-label="Filter by category">${option([['water','Water'],['roads','Roads'],['waste','Waste'],['lights','Electricity'],['health','Public health'],['spaces','Public spaces'],['other','Other']],f.category,'All services')}</select></div><div class="section-row"><h2>${filtered().length} incidents in view</h2><span class="muted">Select any incident to see its evidence and audit trail</span></div><div class="incident-grid" id="exploreGrid">${cards(filtered())}</div>`}
function cards(issues){return issues.map(i=>`<article class="issue-card" data-open="${i.id}" tabindex="0" role="button" aria-label="Explore ${E(i.code)}"><div class="issue-top"><span class="code">${E(i.code)}</span>${badge(i.priority_label)}</div><h3>${E(clip(i.title,92))}</h3><p>${E(clip(i.description,105))}</p><div class="issue-meta"><span>${I('pin')} ${E(i.ward)}</span><span>${I('users')} ${i.report_count} reports</span><span>${badge(i.status,'status')}</span><span class="issue-score">${i.priority}<small>/100</small></span></div></article>`).join('')||'<div class="panel empty-state">No incidents match these filters.</div>'}
function report(){
  return `${heading('CITIZEN PORTAL','Report a civic issue','You describe the problem. NEXUS discovers the service, explains urgency and detects related incidents.')}<div class="form-layout"><section class="panel form-panel"><h2>Tell us what happened</h2><p class="form-help">Your report becomes a trackable incident or is linked to an existing civic signal in the same area.</p><form id="reportForm"><div class="form-group"><label for="reportName">Your display name *</label><input id="reportName" name="name" minlength="2" maxlength="45" placeholder="e.g. Ananya" required autocomplete="name"/><small>Use a non-sensitive nickname for this open demonstration.</small></div><div class="form-group"><label for="reportDescription">Describe the problem *</label><textarea id="reportDescription" name="description" minlength="18" maxlength="1600" placeholder="e.g. The water pipeline has burst beside a school and is flooding the road. Children cannot cross safely..." required></textarea><small>Include what, where, and how it affects public safety. English and a limited set of Tamil service terms are supported.</small></div><div class="two-fields"><div class="form-group"><label for="reportWard">City ward / area *</label><select id="reportWard" name="ward" required><option value="">Choose a ward</option>${wards.map(w=>`<option>${E(w)}</option>`).join('')}</select></div><div class="form-group"><label for="reportLocation">Street or landmark</label><input id="reportLocation" name="location" maxlength="150" placeholder="e.g. School Road" /></div></div><div class="form-foot"><span>Public demonstration: don't enter private contact information or a real emergency.</span><button type="submit" class="btn primary" id="reportSubmit">${I('send')} Submit civic report</button></div></form></section>
  <aside class="panel ai-panel"><div class="ai-head"><span class="ai-icon">${I('spark')}</span><div><h2>Live AI pre-triage</h2><p>Local text classification + explainable impact score</p></div></div><div id="triagePreview">${triageEmpty()}</div><div class="info-note">Our model produces advisory suggestions, not emergency-service dispatch decisions. A municipal officer should validate important cases.</div></aside></div>`;
}
function triageEmpty(){return `<div class="empty-state">${I('spark')}<h3>Intelligence starts with context</h3><p>Start typing a complaint to preview its likely service department, priority and reasoning. No paid API required.</p></div>`}
function triagePreview(r){return `<div class="ai-status"><span class="ai-key">Predicted service</span><div class="ai-big">${E(r.category)}</div><div class="muted">Suggested routing: ${E(r.department)}</div></div><div class="ai-status"><span class="ai-key">Impact assessment</span><div class="issue-top"><span class="ai-big">${r.score}<small class="muted"> / 100</small></span>${badge(r.label)}</div><div class="muted">Local ML confidence ${Math.round(r.confidence*100)}% · advisory classification</div></div><div class="ai-key">Why this priority?</div><ul class="why-list">${r.reasons.map(reason=>`<li>${E(reason)}</li>`).join('')}</ul>`}
function radar(){const alerts=state.overview.radar;return `${heading('CIVIC EARLY-WARNING','Signal Radar','Recognize clusters and potential hazards from real reported signals — not speculative future predictions.',`<button class="btn secondary" data-view="guide">${I('spark')} Ask CivicGuide</button>`)}<div class="stats-grid">${statCard('Amplifying clusters',alerts.filter(a=>a.incident.report_count>=3).length,'3+ reports linked','radio')}${statCard('Early clusters',alerts.filter(a=>a.incident.report_count===2).length,'2 independent reports','users','blue')}${statCard('Severe alerts',alerts.filter(a=>a.incident.priority>=78).length,'High-safety-risk signals','alert','orange')}${statCard('Issues monitored',state.overview.stats.active,'Open civic incidents','eye','purple')}</div><div class="radar-grid"><section class="panel"><div class="panel-heading"><div><h2>What needs attention?</h2><p>Corroboration and severity-based observation alerts</p></div>${badge('Active')}</div>${alerts.map(a=>`<div class="radar-alert" data-open="${a.incident.id}" tabindex="0" role="button"><span class="radar-icon">${I('radio')}</span><div><strong>${E(a.incident.code)} · ${E(clip(a.incident.title,100))}</strong><p>${E(a.reason)} · ${E(a.incident.ward)} · ${a.incident.report_count} voices</p>${badge(a.incident.priority_label)}</div></div>`).join('')||'<div class="empty-state"><p>No clusters or severe warnings yet.</p></div>'}</section><section class="panel"><div class="panel-heading"><div><h2>Why a signal matters</h2><p>Explainability before automation</p></div></div><div class="methodology"><div class="method-row"><span>Shared location and category</span><strong>Conservative matching</strong></div><div class="method-row"><span>Multiple independent observations</span><strong>Confidence signal</strong></div><div class="method-row"><span>Danger or vulnerable settings</span><strong>Safety emphasis</strong></div><div class="method-row"><span>Long waiting time</span><strong>Escalation</strong></div><div class="method-row"><span>Popularity bias control</span><strong>Reports capped at +12</strong></div></div><div class="note">This radar observes reported complaints; it does not establish actual hazards or predict future incidents. Officers must confirm conditions.</div></section></div>`}
function verify(){let pending=state.incidents.filter(i=>i.status==='verification');let resolved=state.incidents.filter(i=>i.status==='resolved');let reopened=state.incidents.filter(i=>i.status==='reopened');return `${heading('THE NEXUS TRUST LOOP','Proof of Resolution','A "completed" task is different from a confirmed improvement in real life.')}
  <div class="steps"><div class="panel step"><div class="step-index">01</div><h3>Officer documents the repair</h3><p>A staff member moves work into verification, records what was fixed, and can attach on-the-ground photo evidence.</p></div><div class="panel step"><div class="step-index">02</div><h3>Resident checks the outcome</h3><p>A citizen who originally reported or corroborated the incident can confirm the repair or flag that the problem still exists.</p></div><div class="panel step"><div class="step-index">03</div><h3>Disputed cases reopen</h3><p>If the repair fails verification, the incident returns to the operational queue with an auditable timeline of the dispute.</p></div></div>
  <div class="stats-grid">${statCard('Awaiting verification',pending.length,'Citizen confirmation pending','clock','purple')}${statCard('Verified fixes',resolved.length,'Reporter-confirmed resolutions','shield')}${statCard('Disputed / reopened',reopened.length,'Re-entered officer queue','refresh','orange')}${statCard('Total civic incidents',state.incidents.length,'Publicly trackable incidents','layers','blue')}</div>
  <div class="section-row"><h2>Cases awaiting resident feedback</h2><span class="muted">Open an incident to confirm or dispute a fix</span></div><section class="panel">${table(pending,20)}</section><div class="note">Identity verification is simplified for this hackathon demo. A production municipality must authenticate actual residents before accepting feedback as proof.</div>`}
function officer(){if(state.auth.role==='citizen')return `${heading('MUNICIPAL OPERATIONS','Officer Workspace','Resolve incidents with clear audit trails, transparent decisions, and citizen-verified closure.')}
  <div class="panel empty-state">${I('lock')}<h3>Protected officer operations</h3><p>Sign in with the demo officer or city administrator credentials to assign, start and submit repairs for verification. Civic reporting remains publicly accessible.</p><button class="btn primary" data-login="1">${I('lock')} Sign in as officer</button></div>`;
 const active=state.incidents.filter(i=>i.status!=='resolved');return `${heading('MUNICIPAL OPERATIONS','Officer Workspace','Take action on reports and retain a transparent history of every decision.',`<span class="badge-pill resolved">${E(state.auth.name)} signed in</span>`)}
 <div class="stats-grid">${statCard('Unassigned',active.filter(i=>i.status==='reported'||i.status==='reopened').length,'New or disputed cases','alert','orange')}${statCard('Assigned',active.filter(i=>i.status==='assigned').length,'Waiting for field work','flag','blue')}${statCard('In progress',active.filter(i=>i.status==='in_progress').length,'On-site operations','refresh')}${statCard('Verify with citizens',active.filter(i=>i.status==='verification').length,'Ready for feedback','shield','purple')}</div><div class="panel"><div class="panel-heading"><div><h2>Operational response queue</h2><p>Open any case to update its workflow and attach repair evidence.</p></div><button class="text-link" id="refreshQueue">Refresh ↻</button></div>${table(active,100)}</div><div class="note">Action controls use signed officer sessions and a request verification token. They are not accessible through the public citizen workflow.</div>`;}
function analytics(){const x=state.overview;const adminView=state.auth.role==='admin'?`<section class="panel"><div class="panel-heading"><div><h2>Administrator planning brief</h2><p>Management recommendations from unresolved incidents (not automatic dispatch decisions)</p></div><span class="badge-pill resolved">Admin workspace</span></div>${state.incidents.filter(i=>i.status!=='resolved').slice(0,3).map(i=>`<div class="signal-item" data-open="${i.id}" tabindex="0" role="button"><span class="signal-num">${i.priority}</span><div class="signal-main"><div class="signal-title">Review ${E(i.code)} — ${E(i.ward)}</div><div class="signal-meta">${E(i.department)} · ${E(i.priority_label)} · ${i.report_count} reports</div></div></div>`).join('')}</section>`:'';return `${heading('PUBLIC INTEREST DASHBOARD','City Intelligence','Understand where civic demand is growing, with transparent data and no inflated accuracy claims.')}
  <div class="stats-grid">${statCard('Civic incidents',x.stats.incidents,'Distinct problem clusters','layers')}${statCard('Total reports',x.stats.voices,'Individual submissions','users','blue')}${statCard('Reports per incident',(x.stats.voices/Math.max(1,x.stats.incidents)).toFixed(1),'Consolidation signal','radio','orange')}${statCard('Verified closure rate',Math.round(x.stats.verified_fixes/Math.max(1,x.stats.incidents)*100)+'%','Citizen-confirmed cases / all','shield','purple')}</div><div class="dashboard-columns"><section class="panel"><div class="panel-heading"><div><h2>Service areas</h2><p>Where the community is raising concerns</p></div></div>${bars(x.categories,12)}</section><section class="panel"><div class="panel-heading"><div><h2>Geographic distribution</h2><p>Reported incidents per ward</p></div></div>${bars(x.wards,12)}</section></div><section class="panel"><div class="panel-heading"><div><h2>Resolution pipeline</h2><p>Every case is traceable from new report to verified outcome</p></div></div>${bars(Object.fromEntries(Object.entries(x.statuses).map(([k,v])=>[niceStatus(k),v])),12)}</section><div class="note">These are counts derived from the demonstration database, not real municipal statistics. This model has not been externally validated for decision-making accuracy or fairness.</div>${adminView}`}
function guide(){return `${heading('CONTEXT-AWARE CIVIC ASSISTANT','Meet CivicGuide','A helpful city-service copilot that understands live incident context and explains its reasoning.')}
  ${state.focusIncident?`<div class="note">Assistant context: <strong>${E(state.focusIncident.code)}</strong> · ${E(state.focusIncident.ward)}. Ask about its status or priority. <button class="text-link" data-clear-context="1">Clear case context</button></div>`:''}<div class="guide-layout"><section class="panel chatbox"><div class="chat-header"><span class="ai-icon">${I('spark')}</span><div><h2>CivicGuide · NEXUS intelligence</h2><p>Powered by local service classification and current incident data</p></div></div><div id="chatMessages" class="chat-messages" aria-live="polite">${state.chat.map(x=>`<div class="bubble ${x.who}">${E(x.text)}</div>`).join('')}</div><div class="chat-suggestions">${state.suggestions.map(x=>`<button class="chip" data-ask="${E(x)}">${E(x)}</button>`).join('')}</div><form id="chatForm" class="chat-form"><input id="chatInput" maxlength="900" minlength="3" required aria-label="Ask CivicGuide" placeholder="Ask about a problem, priority, or incident..." autocomplete="off"/><button type="submit" aria-label="Send message">${I('send')}</button></form></section>
  <aside class="panel guide-tips"><h3>Ask me about...</h3><p>I use current case details, explicit decision rules, and text classification to answer common civic questions.</p><div class="tip" data-ask="Show urgent cases">${I('radio')} What urgent cases need attention?</div><div class="tip" data-ask="How is priority decided?">${I('spark')} Why did AI prioritize a complaint?</div><div class="tip" data-ask="How is a fix verified?">${I('shield')} How are failed repairs reopened?</div><div class="tip" data-ask="How do I report an issue?">${I('plus')} Help me file my first report</div><div class="note">CivicGuide is a local, context-aware assistant with deterministic response logic and a trained text classifier. It is not a general-purpose generative language model.</div></aside></div>`}
function render(){
 if(!state.overview)return;
 const renderers={overview,explore,report,radar,verify,officer,analytics,guide};
 $('#mainContent').innerHTML=renderers[state.view]();
 if(state.view==='explore')bindFilters();
 if(state.view==='report')bindReport();
 if(state.view==='guide')bindGuide();
 if(state.view==='analytics'||state.view==='overview'){};
}
function bindFilters(){
 ['status','ward','category'].forEach(k=>$('#'+k+'Filter')?.addEventListener('change',ev=>{state.filter[k]=ev.target.value;$('#exploreGrid').innerHTML=cards(filtered());$('.section-row h2').textContent=filtered().length+' incidents in view';}));
 $('#issueSearch')?.addEventListener('input',ev=>{state.filter.q=ev.target.value;$('#exploreGrid').innerHTML=cards(filtered());$('.section-row h2').textContent=filtered().length+' incidents in view';});
}
let triageTimer=0;
function bindReport(){
 $('#reportDescription').addEventListener('input',ev=>{
  clearTimeout(triageTimer);const text=ev.target.value;
  if(text.length<8){$('#triagePreview').innerHTML=triageEmpty();return;}
  triageTimer=setTimeout(async()=>{try{const a=await post('/api/triage',{description:text});if($('#reportDescription')?.value===text)$('#triagePreview').innerHTML=triagePreview(a);}catch{$('#triagePreview').innerHTML='<p class="muted">Unable to preview this description.</p>';}},350);
 });
 $('#reportForm').addEventListener('submit',async ev=>{
  ev.preventDefault();const b=$('#reportSubmit');b.disabled=true;b.textContent='Analyzing and submitting…';
  const form=new FormData(ev.currentTarget);
  try{const res=await post('/api/complaints',{name:form.get('name'),description:form.get('description'),ward:form.get('ward'),location:form.get('location')});
   toast(`${res.code}: ${res.merged?'Your observation was linked to an existing incident.':'New civic incident created.'}`);
   await refresh();await openIncident(res.incident_id);
  }catch(err){toast(err.message,true)}finally{b.disabled=false;b.innerHTML=`${I('send')} Submit civic report`;}
 });
}
function bindGuide(){
 const msg=$('#chatMessages');msg.scrollTop=msg.scrollHeight;
 $('#chatForm').addEventListener('submit',async ev=>{ev.preventDefault();const input=$('#chatInput');const value=input.value.trim();if(value.length<3)return;input.value='';await ask(value)});
}
async function ask(message){
 state.chat.push({who:'user',text:message});state.suggestions=[];
 if(state.view==='guide'){const messages=$('#chatMessages');messages.innerHTML=state.chat.map(x=>`<div class="bubble ${x.who}">${E(x.text)}</div>`).join('')+`<div class="bubble bot">Thinking with civic context…</div>`;messages.scrollTop=messages.scrollHeight;}
 try{const reply=await post('/api/assistant',{message,incident_id:state.focusIncident?.id||null});state.chat.push({who:'bot',text:reply.answer});state.suggestions=reply.suggestions||[];}
 catch(err){state.chat.push({who:'bot',text:'I could not retrieve the civic context: '+err.message});}
 if(state.view==='guide')render();
}
function evidenceBlock(e){return e.attachment&&/^\/uploads\/[a-zA-Z0-9-]+\.(?:png|jpg|webp)$/.test(e.attachment)?`<a href="${E(e.attachment)}" target="_blank" rel="noopener noreferrer"><img class="evidence-image" src="${E(e.attachment)}" alt="Repair evidence attached to the incident" loading="lazy"/></a>`:''}
async function openIncident(id){
 $('#drawerBackdrop').classList.remove('hidden');$('#incidentDrawer').classList.remove('hidden');$('#drawerBackdrop').setAttribute('aria-hidden','false');
 $('#drawerContent').innerHTML='<div class="loading"><div class="spinner"></div></div>';
 try{const d=await api('/api/incidents/'+Number(id));state.detail=d;state.focusIncident={id:d.id,code:d.code,ward:d.ward};renderDrawer(d);}
 catch(err){$('#drawerContent').innerHTML=`<div class="empty-state"><h3>Could not load incident</h3><p>${E(err.message)}</p><button class="btn secondary" id="drawerClose">Close</button></div>`;}
}
function renderDrawer(d){
 const isOfficer=state.auth.role!=='citizen';
 let action='';if(isOfficer&&['reported','reopened','assigned','in_progress'].includes(d.status)){
  const k=d.status==='assigned'?'start':d.status==='in_progress'?'request_verification':'assign';
  const name={assign:'Assign to department',start:'Start on-ground work',request_verification:'Submit repair for verification'}[k];
  action=`<form id="actionForm"><input type="hidden" name="action" value="${k}"/><div class="form-group"><label for="actNote">${E(name)} — action note *</label><textarea id="actNote" name="note" minlength="${k==='request_verification'?'20':'8'}" required placeholder="Explain what action was taken and what evidence supports it" ></textarea></div>${k==='assign'?`<div class="form-group"><label for="actDept">Department</label><input id="actDept" name="department" value="${E(d.department)}" maxlength="90"/></div>`:''}<button class="btn primary full" type="submit">${I('check')} ${E(name)}</button></form>`;
 }
 const verification=d.status==='verification'?`<form id="verifyForm"><div class="form-group"><label for="verifyName">Your original reporter display name *</label><input id="verifyName" name="name" required minlength="2" maxlength="45" placeholder="Name used on your complaint"/></div><div class="form-group"><label for="verdict">What did you observe?</label><select id="verdict" name="verdict"><option value="confirm">Confirm — the problem is fixed</option><option value="dispute">Dispute — the problem remains</option></select></div><div class="form-group"><label for="verifyNote">Explain what you found *</label><textarea id="verifyNote" name="note" minlength="8" maxlength="800" required placeholder="Tell us whether the repair worked in practice"></textarea></div><button class="btn primary full" type="submit">${I('shield')} Send outcome verification</button></form>`:'';
 const support=d.status!=='resolved'?`<form id="supportForm"><div class="two-fields"><div class="form-group"><label for="supportName">Your display name</label><input id="supportName" name="name" required minlength="2" maxlength="45" placeholder="e.g. Arun"/></div><div class="form-group"><label for="supportNote">What did you observe?</label><input id="supportNote" name="note" required minlength="8" maxlength="600" placeholder="Describe your experience"/></div></div><button class="btn secondary" type="submit">${I('users')} Corroborate this issue</button></form>`:'';
 const evidence=isOfficer&&['in_progress','verification'].includes(d.status)?`<form id="evidenceForm"><div class="form-group"><label for="evidenceKind">Evidence phase</label><select id="evidenceKind" name="kind"><option value="before">Before repair</option><option value="after">After repair</option></select></div><div class="form-group"><label for="evidenceFile">Photo evidence — PNG, JPG or WebP, up to 2MB</label><input id="evidenceFile" name="file" type="file" accept="image/png,image/jpeg,image/webp" required /></div><button class="btn secondary" type="submit">${I('upload')} Attach evidence</button></form>`:'';
 $('#drawerContent').innerHTML=`<div class="drawer-heading"><div><span class="eyebrow">TRACKED CIVIC INCIDENT</span><h2>${E(d.code)}</h2><div>${badge(d.priority_label)} &nbsp; ${badge(d.status,'status')}</div></div><button class="icon-button" id="drawerClose" aria-label="Close incident details">${I('close')}</button></div><div class="drawer-body">
  <div class="drawer-card"><h3>${E(d.title)}</h3><p>${E(d.description)}</p><div class="drawer-grid spaced-top"><div class="datum"><small>Area</small><strong>${E(d.ward)}</strong></div><div class="datum"><small>Landmark</small><strong>${E(d.location||'Not specified')}</strong></div><div class="datum"><small>AI-classified service</small><strong>${E(d.category)}</strong></div><div class="datum"><small>Responsible department</small><strong>${E(d.department)}</strong></div><div class="datum"><small>Corroborating voices</small><strong>${d.report_count}</strong></div><div class="datum"><small>Last updated</small><strong>${E(niceTime(d.updated_at))}</strong></div></div></div>
  <div class="drawer-card"><div class="panel-heading"><div><h3>Explainable impact score</h3><p>Decision support, not an emergency designation</p></div><span class="ai-big">${d.priority}<small class="muted">/100</small></span></div><ul class="why-list">${(d.priority_reasons||[]).map(r=>`<li>${E(r)}</li>`).join('')}</ul></div>
  ${action?`<div class="drawer-card"><h3>Officer action</h3>${action}</div>`:''}
  ${evidence?`<div class="drawer-card"><h3>Attach repair evidence</h3>${evidence}</div>`:''}
  ${verification?`<div class="drawer-card"><h3>Resident verification</h3><p>For this demo, use a name already associated with this incident. Production identity proof is not implemented.</p><div class="small-spacer"></div>${verification}</div>`:''}
  ${support?`<div class="drawer-card"><h3>Add your observation</h3><p>Support this existing incident rather than creating a duplicate.</p><div class="small-spacer"></div>${support}</div>`:''}
  <div class="drawer-card"><h3>Public audit trail</h3><ul class="timeline">${(d.timeline||[]).map(ev=>`<li><strong>${E(ev.kind.replaceAll('_',' '))} · ${E(ev.actor)}</strong>${E(ev.note)}<br/><span>${E(niceTime(ev.date))}</span>${evidenceBlock(ev)}</li>`).join('')}</ul></div>
  ${d.verifications?.length?`<div class="drawer-card"><h3>Verification rounds</h3>${d.verifications.map(v=>`<p><strong>${E(v.name)} · ${E(v.verdict)}</strong><br/>${E(v.note)}<br/><span class="muted">Round ${v.round} · ${E(niceTime(v.date))}</span></p>`).join('<hr/>')}</div>`:''}
  <div class="drawer-card"><h3>Reporters & observations</h3>${d.reports.map(r=>`<p><strong>${E(r.name)}</strong> <span class="muted">· ${E(niceTime(r.date))}</span><br/>${E(r.description)}</p>`).join('<hr/>')}</div>
 </div>`;
 $('#drawerClose')?.focus();
 $('#actionForm')?.addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.currentTarget);try{await post(`/api/incidents/${d.id}/action`,{action:f.get('action'),actor:state.auth.name,note:f.get('note'),department:f.get('department')||undefined},true);toast('Officer action recorded');await refresh();await openIncident(d.id)}catch(err){toast(err.message,true)}});
 $('#supportForm')?.addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.currentTarget);try{await post(`/api/incidents/${d.id}/support`,{name:f.get('name'),note:f.get('note')});toast('Observation linked to incident');await refresh();await openIncident(d.id)}catch(err){toast(err.message,true)}});
 $('#verifyForm')?.addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.currentTarget);try{const r=await post(`/api/incidents/${d.id}/verify`,{name:f.get('name'),note:f.get('note'),verdict:f.get('verdict')});toast(r.status==='reopened'?'Dispute recorded: issue reopened':'Citizen-confirmed resolution recorded');await refresh();await openIncident(d.id)}catch(err){toast(err.message,true)}});
 $('#evidenceForm')?.addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.currentTarget);const image=f.get('file');if(image.size>2_000_000){toast('Maximum image size is 2 MB',true);return;}try{const res=await api(`/api/incidents/${d.id}/evidence?kind=${encodeURIComponent(f.get('kind'))}&name=${encodeURIComponent(state.auth.name)}`,{method:'POST',headers:{'X-CSRF-Token':state.auth.csrf},body:new FormData(ev.currentTarget)});toast('Evidence attached successfully');await openIncident(d.id)}catch(err){toast(err.message,true)}});
}
function closeDrawer(){state.detail=null;$('#drawerBackdrop').classList.add('hidden');$('#incidentDrawer').classList.add('hidden');$('#drawerBackdrop').setAttribute('aria-hidden','true')}
function loginModal(){
 $('#modalBackdrop').classList.remove('hidden');$('#authModal').classList.remove('hidden');
 const loggedIn=state.auth.role!=='citizen';
 $('#authContent').innerHTML=`<div class="modal-head"><span class="eyebrow">${loggedIn?'ACTIVE SESSION':'AUTHORIZED OPERATIONS'}</span><button class="icon-button" id="modalClose" aria-label="Close sign-in window">${I('close')}</button></div><h2 id="authTitle">${loggedIn?'Officer signed in':'Sign in to CivicResolve'}</h2><p>${loggedIn?'Switch back to the public citizen portal by ending your authenticated session.':'Officer functions require a signed session. To test the workflow, use one of the demonstration accounts below.'}</p>${loggedIn?`<button class="btn warn full" id="logoutBtn">Sign out</button>`:`<div class="demo-box"><strong>Hackathon demo accounts</strong><br/>Officer: <code>officer@nexus.demo</code><br/>Admin: <code>admin@nexus.demo</code><br/>Demo password: <code>NexusDemo#2026</code><br/><small>For demonstration only, not real municipal credentials.</small></div><form id="loginForm"><div class="form-group"><label for="loginEmail">Demo account email</label><input type="email" id="loginEmail" name="email" required value="officer@nexus.demo" autocomplete="username"/></div><div class="form-group"><label for="loginPassword">Demo password</label><input type="password" id="loginPassword" name="password" required value="NexusDemo#2026" autocomplete="current-password"/></div><button class="btn primary full" type="submit">${I('lock')} Start authorized session</button></form>`}`;
 $('#modalClose').addEventListener('click',closeModal);
 $('#loginForm')?.addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.currentTarget);try{state.auth=await post('/api/auth/login',{email:f.get('email'),password:f.get('password')});toast('Signed in as '+state.auth.name);closeModal();await refresh();go('officer')}catch(err){toast(err.message,true)}});
 $('#logoutBtn')?.addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'});toast('Signed out');closeModal();await refresh();go('overview')}catch(err){toast(err.message,true)}});
 $('#loginEmail')?.focus();
}
function closeModal(){$('#modalBackdrop').classList.add('hidden');$('#authModal').classList.add('hidden')}

document.addEventListener('click',event=>{
  if(event.target.closest('[data-view]')){go(event.target.closest('[data-view]').dataset.view);return;}
  if(event.target.closest('[data-open]')){openIncident(event.target.closest('[data-open]').dataset.open);return;}
  if(event.target.closest('[data-login]')){loginModal();return;}
  if(event.target.closest('[data-clear-context]')){state.focusIncident=null;render();return;}
  if(event.target.closest('[data-ask]')){const message=event.target.closest('[data-ask]').dataset.ask;go('guide');ask(message);return;}
  if(event.target.closest('#loginButton')){loginModal();return;}
  if(event.target.closest('#menuToggle')){$('#sidebar').classList.toggle('open');return;}
  if(event.target.closest('#drawerClose')||event.target.id==='drawerBackdrop'){closeDrawer();return;}
  if(event.target.id==='modalBackdrop'){closeModal();return;}
  if(event.target.closest('#refreshQueue')){refresh(true);return;}
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'){closeDrawer();closeModal();$('#sidebar').classList.remove('open');}
  if((event.key==='Enter'||event.key===' ')&&event.target.matches('[data-open][role="button"]')){event.preventDefault();openIncident(event.target.dataset.open);}
});

refresh(true).then(()=>{
  const url=new URL(location.href);const id=Number(url.searchParams.get('incident'));
  if(Number.isInteger(id)&&id>0)openIncident(id);
});
