import {api,BASE_API} from './api.js';
import {TransactionGraph} from './graph.js';
import {$,$$,escapeHTML as h,number,decimal,nameDetector,nameFactor,explainDetector,stepRange,shortId} from './format.js';

const pageLimit=15;
const state={summary:null,queue:[],total:0,offset:0,selectedId:null,case:null,tab:'evidence',selectedTx:null,focusedAccount:null,selectedAlertId:null,stressMode:'transaction',stressAlertId:null,stressTx:null,stressResult:null,stressResultTarget:null,stressLoading:false,stressToken:0,query:'',detector:'',minPriority:0,reviewStatus:'all',reviewStatuses:{},reviewCounts:{to_do:0,in_progress:0,done:0},queueToken:0,caseToken:0,online:false,staged:false,loadingAnalysis:false};
const graph=new TransactionGraph($('#graph-surface'),{onAccount:account=>selectAccount(account),onTransaction:tx=>selectTransaction(tx)});
const bind=(selector,event,fn)=>$(selector).addEventListener(event,fn);
function showError(message){$('#error-text').textContent=String(message);$('#error-banner').classList.remove('hidden')}
function hideError(){$('#error-banner').classList.add('hidden')}
function setConnection(online){state.online=online;$('#connection-pill').classList.toggle('offline',!online);$('#connection-text').textContent=online?'Backend online':'Backend offline'}
function loading(container,msg){container.innerHTML=`<div class="loading-placeholder">${h(msg)}</div>`}
function empty(container,title,msg){container.innerHTML=`<div class="empty-state"><strong>${h(title)}</strong>${h(msg)}</div>`}
async function bootstrap(){
  hideError();
  try{
    const [health,summary,meta]=await Promise.all([api.health(),api.summary(),api.meta()]);
    if(!health.ready || health.time_unit!=='simulation_step'||summary.time_unit!=='simulation_step'||meta.score_is_probability!==false)throw new Error('Backend data contract differs from expected native-step schema');
    state.summary=summary;setConnection(true);renderSummary();state.offset=0;await loadCases();route();
  }catch(e){setConnection(false);showError(e.message);if(!state.case){empty($('#case-list'),'Backend unavailable','Start Uvicorn on port 8000 and click Retry.');loading($('#graph-surface'),'Waiting for backend');empty($('#timeline'),'No transaction data','');empty($('#intel-content'),'No investigation selected','')}}
}
function renderSummary(){const s=state.summary;if(!s)return;
  $('#stat-transactions').textContent=number(s.transactions??s.input_transactions);
  $('#stat-alerts').textContent=number(s.alerts??s.input_alerts);
  $('#stat-cases').textContent=number(s.cases);
  $('#run-id').textContent=s.run_id||'UNKNOWN';
}
function renderReviewCounts(){
  const counts=state.reviewCounts;
  $('#count-to-do').textContent=number(counts.to_do);$('#review-count-to-do').textContent=number(counts.to_do);
  $('#count-in-progress').textContent=number(counts.in_progress);$('#review-count-in-progress').textContent=number(counts.in_progress);
  $('#count-done').textContent=number(counts.done);$('#review-count-done').textContent=number(counts.done);
}
async function loadCases(){const token=++state.queueToken;loading($('#case-list'),'Retrieving prioritized cases…');
  try{const response=await api.cases({limit:pageLimit,offset:state.offset,minPriority:state.minPriority,detector:state.detector,search:state.query,reviewStatus:state.reviewStatus});if(token!==state.queueToken)return;
    if(state.summary && response.run_id!==state.summary.run_id){await bootstrap();return}
    if(state.offset>=response.total&&state.offset>0){state.offset=response.total?Math.floor((response.total-1)/pageLimit)*pageLimit:0;return loadCases()}
    state.queue=response.items;state.total=response.total;state.reviewCounts=response.review_counts;
    for(const item of response.items)state.reviewStatuses[item.case_id]=item.review_status;
    renderQueue();renderReviewCounts();renderOverviewCases();
  }catch(e){if(token!==state.queueToken)return;showError(e.message);empty($('#case-list'),'Could not load cases',e.message)}
}
function renderQueue(){$('#queue-total').textContent=number(state.total);
  const list=$('#case-list');
  if(!state.queue.length){empty(list,'No matching cases','Try another search, detector or priority threshold.');}
  else{list.innerHTML=state.queue.map((c,i)=>`<article class="review-item"><button type="button" class="case-item ${state.selectedId===c.case_id?'selected':''}" data-case-id="${h(c.case_id)}" aria-pressed="${state.selectedId===c.case_id}"><div class="case-item-top"><span class="case-rank">${String(state.offset+i+1).padStart(2,'0')}</span><span class="case-id">${h(shortId(c.case_id))}</span><span class="case-score">${decimal(c.priority_score).replace('.00','')}</span></div><div class="case-tagline">${h(c.detector_types.map(nameDetector).join(' · '))}</div><div class="case-mini"><span>${number(c.alert_count)} alerts</span><span>${number(c.evidence_count)} transfers</span><span>${h(stepRange(c))}</span></div></button><label class="status-select-label"><span class="sr-only">Review status for case ${h(shortId(c.case_id))}</span><select class="status-select" data-review-case="${h(c.case_id)}"><option value="to_do" ${c.review_status==='to_do'?'selected':''}>To do</option><option value="in_progress" ${c.review_status==='in_progress'?'selected':''}>In progress</option><option value="done" ${c.review_status==='done'?'selected':''}>Done</option></select></label></article>`).join('');
    $$('.case-item',list).forEach(item=>item.addEventListener('click',()=>openCase(item.dataset.caseId)));
    $$('.status-select',list).forEach(select=>select.addEventListener('change',()=>updateReviewStatus(select.dataset.reviewCase,select.value)));
  }
  $('#pagination-label').textContent=state.total?`${number(state.offset+1)}–${number(Math.min(state.offset+pageLimit,state.total))} of ${number(state.total)}`:'0 results';
  $('#prev-page').disabled=state.offset===0;$('#next-page').disabled=state.offset+pageLimit>=state.total;
}
function renderOverviewCases(){
  const list=$('#overview-cases');
  if(!state.queue.length){empty(list,'No cases in this view','Open Case reviews to change filters.');return}
  list.innerHTML=state.queue.slice(0,5).map((c,i)=>`<button class="overview-case" type="button" data-case-id="${h(c.case_id)}"><span class="overview-rank">${String(state.offset+i+1).padStart(2,'0')}</span><span class="overview-case-main"><strong>${h(shortId(c.case_id))}</strong><small>${h(c.detector_types.map(nameDetector).join(' · '))}</small></span><span class="overview-priority">${decimal(c.priority_score).replace('.00','')}</span><span class="status-badge status-${h(c.review_status)}">${h(c.review_status.replace('_',' '))}</span></button>`).join('');
  $$('.overview-case',list).forEach(button=>button.addEventListener('click',()=>openCase(button.dataset.caseId)));
}
function showPage(page){
  const pages={overview:'#overview-page',reviews:'#reviews-page',case:'#case-page',methodology:'#methodology-page'};
  for(const [name,selector] of Object.entries(pages))$(selector).classList.toggle('hidden',name!==page);
  $$('[data-nav]').forEach(link=>link.classList.toggle('nav-active',link.dataset.nav===page));
}
function route(){
  const [page='overview', ...parts]=location.hash.slice(1).split('/');
  if(page==='case'){
    showPage('case');
    const id=parts.join('/');
    if(id&&(state.selectedId!==decodeURIComponent(id)||!state.case))loadCase(decodeURIComponent(id));
    return;
  }
  showPage(['overview','reviews','methodology'].includes(page)?page:'overview');
}
function openCase(id){
  const next=`#case/${encodeURIComponent(id)}`;
  if(location.hash===next)route();else location.hash=next;
}
async function updateReviewStatus(caseId,status){
  try{
    const result=await api.setReviewStatus(caseId,status);
    state.reviewStatuses[caseId]=result.status;
    if(state.case?.case_id===caseId)$('#case-review-status').value=result.status;
    await loadCases();
  }catch(e){showError(e.message);await loadCases()}
}
function clearCase(){state.selectedId=null;state.case=null;state.selectedTx=null;state.focusedAccount=null;state.selectedAlertId=null;state.stressAlertId=null;state.stressToken++;state.stressLoading=false;state.stressResult=null;graph.setData(null);
  $('#selected-case-title').textContent='Transaction network';$('#selected-case-meta').textContent='Select a case to inspect source evidence';$('#priority-score').textContent='—';$('#timeline-counter').textContent='—';empty($('#intel-content'),'No case selected','Select a case from the queue');empty($('#timeline'),'No transfers to show','');}
async function loadCase(id){if(!id)return;state.selectedId=id;state.case=null;state.stressToken++;state.stressLoading=false;state.stressResult=null;state.stressResultTarget=null;state.stressAlertId=null;state.stressMode='transaction';state.selectedTx=null;state.focusedAccount=null;state.selectedAlertId=null;state.stressTx=null;const token=++state.caseToken;renderQueue();
  $('#selected-case-title').textContent=`Case ${shortId(id)}`;
  $('#selected-case-meta').textContent='Loading verified case evidence…';loading($('#graph-surface'),'Building directed transaction graph…');loading($('#timeline'),'Loading timeline…');loading($('#intel-content'),'Retrieving risk factors and alerts…');
  try{const detail=await api.case(id);if(token!==state.caseToken)return;
    if(detail.case_id!==id || detail.time_unit!=='simulation_step' ||detail.score_is_probability!==false)throw new Error('Case detail violates the agreed backend contract');
    state.case=detail;
    state.reviewStatuses[id]=detail.review_status||'to_do';
    $('#case-review-status').value=state.reviewStatuses[id];
    state.stressTx=detail.transactions?.[0]?.transaction_id||null;
    graph.setData(detail.graph);
    $('#selected-case-meta').textContent=`${number(detail.account_ids.length)} accounts  ·  ${number(detail.evidence_count)} transactions  ·  ${stepRange(detail)}`;
    $('#priority-score').textContent=decimal(detail.priority_score);
    $('#graph-size').textContent=`${detail.graph.nodes.length} nodes · ${detail.graph.edges.length} edges`;
    renderTimeline();renderIntel();
  }catch(e){if(token!==state.caseToken)return;showError(e.message);empty($('#graph-surface'),'Case unavailable',e.message);empty($('#intel-content'),'Could not load this case',e.message)}
}
function selectAccount(account){
  if(!state.case)return;
  state.focusedAccount=state.focusedAccount===account?null:account;
  state.selectedAlertId=null;state.selectedTx=null;
  state.stressToken++;state.stressLoading=false;state.stressResult=null;
  const transactions=state.case.transactions.filter(tx=>!state.focusedAccount||tx.source_account===state.focusedAccount||tx.destination_account===state.focusedAccount);
  if(!transactions.some(tx=>tx.transaction_id===state.stressTx))state.stressTx=transactions[0]?.transaction_id||null;
  graph.setSelection(null,state.focusedAccount);renderTimeline();renderIntel();
}
function selectTransaction(txid){if(!state.case)return;state.selectedAlertId=null;state.selectedTx=txid;state.stressTx=txid;state.stressToken++;state.stressLoading=false;state.stressResult=null;graph.setSelection(txid,state.focusedAccount);renderTimeline();renderIntel();}
function selectPattern(alertId){
  const alert=state.case?.alerts.find(item=>item.alert_id===alertId);
  if(!alert)return;
  state.selectedAlertId=state.selectedAlertId===alertId?null:alertId;
  state.focusedAccount=null;state.selectedTx=null;
  if(state.selectedAlertId)graph.setPatternSelection(alert.transaction_ids);
  else graph.setSelection(null,null);
  renderTimeline();renderIntel();
}
function clearEvidenceFilter(){
  state.selectedAlertId=null;state.focusedAccount=null;state.selectedTx=null;
  state.stressTx=state.case?.transactions[0]?.transaction_id||null;
  state.stressToken++;state.stressLoading=false;state.stressResult=null;
  graph.setSelection(null,null);renderTimeline();renderIntel();
}
function renderTimeline(){const c=state.case;if(!c){empty($('#timeline'),'No timeline','');return}
 const txs=[...c.transactions].sort((a,b)=>a.simulation_step-b.simulation_step||a.transaction_id.localeCompare(b.transaction_id));
 const selectedAlert=c.alerts.find(alert=>alert.alert_id===state.selectedAlertId);
 const patternIds=selectedAlert?new Set(selectedAlert.transaction_ids):null;
 const focused=patternIds?txs.filter(t=>patternIds.has(t.transaction_id)):state.focusedAccount?txs.filter(t=>t.source_account===state.focusedAccount||t.destination_account===state.focusedAccount):txs;
 const filtered=focused;
 $('#timeline-counter').textContent=`${number(filtered.length)} of ${number(txs.length)} transfers`;
 $('#focus-description').textContent=selectedAlert?`Showing ${number(filtered.length)} transfers for ${nameDetector(selectedAlert.detector)} pattern`:state.focusedAccount?`Showing transfers touching account ${state.focusedAccount}`:'Click a graph node or edge to inspect evidence';
 $('#clear-focus').textContent=selectedAlert?'Clear pattern filter ×':'Clear account filter ×';
 $('#clear-focus').classList.toggle('hidden',!state.focusedAccount&&!selectedAlert);
 const container=$('#timeline');if(!filtered.length){empty(container,'No matching transactions','');return}
 container.innerHTML=filtered.map(t=>`<button class="timeline-row ${state.selectedTx===t.transaction_id?'selected':''}" type="button" data-txid="${h(t.transaction_id)}"><div class="step-badge">STEP ${h(t.simulation_step)}</div><div><div class="timeline-flow"><span>${h(t.source_account)}</span><em>→</em><span>${h(t.destination_account)}</span></div><div class="timeline-id mono">${h(t.transaction_id)}</div></div><div class="timeline-amount">${decimal(t.amount)}<br><span class="muted small">units</span></div></button>`).join('');
 $$('.timeline-row',container).forEach(b=>b.addEventListener('click',()=>selectTransaction(b.dataset.txid)));
 if(state.selectedTx){const sel=$('.timeline-row.selected',container);if(sel)sel.scrollIntoView({block:'nearest',behavior:'smooth'})}
}
function setTab(tab){state.tab=tab;$$('.tab').forEach(button=>{let selected=button.dataset.tab===tab;button.classList.toggle('active',selected);button.setAttribute('aria-selected',String(selected));});$('#intel-content').setAttribute('aria-labelledby',`tab-${tab}`);renderIntel()}
function renderIntel(){const c=state.case;if(!c){empty($('#intel-content'),'No case selected','');return}
 const content=$('#intel-content');
 if(state.tab==='evidence'){
   const selected=c.transactions.find(t=>t.transaction_id===state.selectedTx);
   let html=`<div class="section-label">CASE OVERVIEW</div><div class="detail-stat-grid"><div class="detail-stat"><span>NETWORK ACCOUNTS</span><strong>${number(c.account_ids.length)}</strong></div><div class="detail-stat"><span>SOURCE TRANSFERS</span><strong>${number(c.evidence_count)}</strong></div><div class="detail-stat"><span>PATTERN ALERTS</span><strong>${number(c.alert_count)}</strong></div><div class="detail-stat"><span>SIMULATION RANGE</span><strong>${h(c.start_step)}–${h(c.end_step)}</strong></div></div>`;
   html+=`<div class="section-label">FLAGGED PATTERNS</div><p class="stress-intro">Select a pattern to show its evidence transfers in the graph and timeline. Select an account to focus its connected transfers.</p><div class="risk-alert-list">${c.alerts.map(alertMarkup).join('')}</div>`;
   if(selected){html+=`<div class="section-label">SELECTED EVIDENCE</div><div class="evidence-highlight"><strong class="mono">${h(selected.transaction_id)}</strong><p>${h(selected.source_account)} → ${h(selected.destination_account)}<br>Amount: ${decimal(selected.amount)} synthetic units · Step ${h(selected.simulation_step)}</p><button type="button" id="stress-selected" class="btn btn-small">Stress-test this transfer →</button></div>`}
   content.innerHTML=html;
   $('#stress-selected')?.addEventListener('click',()=>{state.stressTx=state.selectedTx;setTab('stress')});
   $$('.stress-pattern-action',content).forEach(button=>button.addEventListener('click',()=>openPatternStress(button.dataset.alertId,'pattern')));
   $$('.stress-pattern-transactions',content).forEach(button=>button.addEventListener('click',()=>openPatternStress(button.dataset.alertId,'transaction')));
   $$('.risk-pattern',content).forEach(button=>button.addEventListener('click',()=>selectPattern(button.dataset.riskPattern)));
   $$('.risk-account',content).forEach(button=>button.addEventListener('click',()=>selectAccount(button.dataset.riskAccount)));
 }else if(state.tab==='factors'){
   content.innerHTML=`<div class="section-label">PRIORITY SCORE FACTORS</div><p class="stress-intro">A heuristic investigation-priority score, not a fraud probability. Each bar shows earned points against that factor’s maximum weighted points.</p>${factorMarkup(c.risk_factors)}${scoreFormulaMarkup(c.score_components,c.risk_factors,c.alert_assessments)}`;
 }else{
   const stressAlert=c.alerts.find(alert=>alert.alert_id===state.stressAlertId);
   const candidateTransactions=stressAlert?c.transactions.filter(t=>stressAlert.transaction_ids.includes(t.transaction_id)):c.transactions;
   const availableTransactions=candidateTransactions.filter(t=>stressAlert||!state.focusedAccount||t.source_account===state.focusedAccount||t.destination_account===state.focusedAccount);
   if(!availableTransactions.some(t=>t.transaction_id===state.stressTx))state.stressTx=availableTransactions[0]?.transaction_id||null;
   let options=availableTransactions.map(t=>`<option value="${h(t.transaction_id)}" ${state.stressTx===t.transaction_id?'selected':''}>Step ${h(t.simulation_step)} · ${h(t.source_account)} → ${h(t.destination_account)} · ${decimal(t.amount)} units · ${h(t.transaction_id)}</option>`).join('');
   const patternOptions=c.alerts.map(alert=>`<option value="${h(alert.alert_id)}" ${state.stressAlertId===alert.alert_id?'selected':''}>${h(nameDetector(alert.detector))} · ${number(alert.transaction_ids.length)} transfers · ${h(alert.alert_id)}</option>`).join('');
   const targetDescription=state.stressMode==='pattern'
     ?'All unique transfers flagged for the selected pattern are excluded together.'
     :stressAlert?`Choose one transfer flagged for ${h(nameDetector(stressAlert.detector))}.`:
       state.focusedAccount?`Account ${h(state.focusedAccount)} is selected. Choose one transfer involving this account to test its contribution.`:
       'Choose one transfer in the case, or select a pattern from Evidence to focus its flagged transfers.';
   content.innerHTML=`<div class="section-label">COUNTERFACTUAL EVIDENCE REVIEW</div><p class="stress-intro">${targetDescription} The priority score and factor contributions are recalculated; case membership and original evidence remain unchanged.</p><label for="stress-mode" class="stress-label">Stress-test target</label><select id="stress-mode" class="stress-picker"><option value="transaction" ${state.stressMode==='transaction'?'selected':''}>Individual transaction</option><option value="pattern" ${state.stressMode==='pattern'?'selected':''}>Flagged pattern (all its transfers)</option></select>${state.stressMode==='pattern'?`<label for="stress-pattern" class="stress-label stress-secondary-label">Flagged pattern</label><select id="stress-pattern" class="stress-picker" ${c.alerts.length?'':'disabled'}>${patternOptions}</select>`:`<label for="stress-transaction" class="stress-label stress-secondary-label">Evidence transaction to exclude</label><select id="stress-transaction" class="stress-picker" ${availableTransactions.length?'':'disabled'}>${options}</select>`}<div class="stress-actions"><button type="button" id="run-stress" class="btn btn-primary" ${state.stressLoading||!(state.stressMode==='pattern'?c.alerts.length:availableTransactions.length)?'disabled':''}>${state.stressLoading?'Recalculating…':'Run Stress Test'}</button><button type="button" id="reset-stress" class="btn btn-secondary" ${state.stressResult?'':'disabled'}>Reset</button></div><div id="stress-output">${state.stressResult?stressMarkup(state.stressResult):'<div class="empty-state"><strong>Ready to challenge the evidence</strong>Choose a transaction or flagged pattern to recalculate its priority index.</div>'}</div>`;
   $('#stress-mode').addEventListener('change',ev=>{state.stressToken++;state.stressLoading=false;state.stressMode=ev.target.value;state.stressResult=null;if(state.stressMode==='pattern'&&!c.alerts.some(alert=>alert.alert_id===state.stressAlertId))state.stressAlertId=c.alerts[0]?.alert_id||null;renderIntel()});
   $('#stress-pattern')?.addEventListener('change',ev=>{state.stressToken++;state.stressLoading=false;state.stressAlertId=ev.target.value;state.stressResult=null;renderIntel()});
   $('#stress-transaction')?.addEventListener('change',ev=>{state.stressToken++;state.stressLoading=false;state.stressTx=ev.target.value;state.stressResult=null;renderIntel()});
   $('#run-stress').addEventListener('click',runStress);
   $('#reset-stress').addEventListener('click',()=>{state.stressToken++;state.stressLoading=false;state.stressResult=null;state.stressResultTarget=null;state.stressTx=availableTransactions[0]?.transaction_id||null;renderIntel()});
 }
}
function alertMarkup(alert){
  const selected=state.selectedAlertId===alert.alert_id;
  const accounts=alert.account_ids||[];
  return `<article class="risk-alert ${selected?'selected':''}"><button type="button" class="risk-pattern" data-risk-pattern="${h(alert.alert_id)}" aria-pressed="${selected}"><span class="risk-pattern-heading"><span class="signal-label">${h(nameDetector(alert.detector))}</span><span class="signal-badge">${number(alert.transaction_ids.length)} flagged transfers</span></span><span class="risk-explanation">${h(alert.reason||explainDetector(alert.detector))}</span><span class="risk-alert-meta mono">${h(alert.alert_id)} · ${h(stepRange(alert))}</span></button><div class="risk-accounts"><span class="section-label">Flagged accounts</span><div class="risk-account-list">${accounts.map(account=>`<button type="button" class="risk-account ${state.focusedAccount===account?'selected':''}" data-risk-account="${h(account)}" aria-pressed="${state.focusedAccount===account}">${h(account)}</button>`).join('')}</div></div><div class="risk-pattern-actions"><button type="button" class="btn btn-small stress-pattern-action" data-alert-id="${h(alert.alert_id)}">Stress-test pattern</button><button type="button" class="btn btn-small stress-pattern-transactions" data-alert-id="${h(alert.alert_id)}">Test an individual transfer</button></div></article>`;
}
function openPatternStress(alertId,mode){
  const alert=state.case?.alerts.find(item=>item.alert_id===alertId);
  if(!alert)return;
  state.stressAlertId=alertId;state.stressMode=mode;state.stressTx=alert.transaction_ids[0]||null;
  state.selectedAlertId=alertId;state.selectedTx=mode==='transaction'?state.stressTx:null;
  state.focusedAccount=null;state.stressToken++;state.stressLoading=false;state.stressResult=null;state.stressResultTarget=null;
  graph.setPatternSelection(alert.transaction_ids);renderTimeline();
  setTab('stress');
}
function factorMarkup(factors){return factors.map(f=>{
  const contribution=Math.max(0,Number(f.contribution)||0);
  const maxPoints=100*(Number(f.base_weight??f.weight)||0);
  const fill=maxPoints>0?Math.min(100,100*contribution/maxPoints):0;
  const signal=f.available?Math.round(100*(f.normalized_value||0)):0;
  return `<div class="factor"><div class="factor-head"><strong>${h(nameFactor(f.name))}</strong><span>${decimal(contribution)} / ${decimal(maxPoints)} pts</span></div><div class="factor-sub"><span>Fixed weight: ${(Number(f.weight)*100).toFixed(0)}%</span><span>${f.available?`${signal}% signal · ${fill.toFixed(1)}% of max points`:'Unavailable · value treated as 0'}</span></div><div class="factor-track" role="img" aria-label="${h(nameFactor(f.name))}: ${decimal(contribution)} of ${decimal(maxPoints)} maximum points, ${fill.toFixed(1)} percent"><div class="factor-fill" style="width:${fill.toFixed(2)}%"></div></div><p class="description">${h(f.description)}</p></div>`;
}).join('')}
function scoreFormulaMarkup(components,factors,assessments){
  if(!components)return '';
  const values=new Map(factors.map(f=>[f.name,f.normalized_value]));
  const assessmentDetails=(assessments||[]).map(item=>`<li><strong>${h(nameDetector(item.detector))}</strong> · ${h(item.alert_id)} · ${item.threshold_met?'active':'inactive'} · severity ${decimal(item.severity)} · ${h(JSON.stringify(item.measured))}</li>`).join('');
  return `<div class="score-formula"><div class="section-label">V2 SCORE FORMULA</div><p>P = 100 × (0.45M + 0.35A + 0.20C)</p><div class="score-formula-values"><span>Pattern strength M <strong>${decimal(values.get('pattern_strength'))}</strong></span><span>Activity anomaly A <strong>${decimal(values.get('activity_anomaly'))}</strong></span><span>Evidence support C <strong>${decimal(values.get('evidence_support'))}</strong></span><span>Weighted total <strong>${decimal(components.weighted_total)}</strong></span></div><p class="score-formula-note">Factors are computed in [0,1]. Their weighted points are rounded to two decimals and summed. These are heuristic priorities, not calibrated probabilities.</p><details class="score-calculation-details"><summary>View factor calculations</summary><ul>${factors.map(f=>`<li><strong>${h(nameFactor(f.name))}:</strong> ${h(f.formula)} · ${h(JSON.stringify(f.raw_value))}${f.transaction_ids.length?` · Supporting evidence: ${f.transaction_ids.map(id=>`<span class="mono">${h(id)}</span>`).join(', ')}`:''}</li>`).join('')}${assessmentDetails}</ul></details></div>`;
}
function stressMarkup(s){
  const before=new Map((s.before_factors||[]).map(f=>[f.name,f]));
  const after=new Map((s.after_factors||[]).map(f=>[f.name,f]));
  const comparisons=[...before.values()].map(f=>{
    const next=after.get(f.name);
    return {name:f.name,before:f.contribution||0,after:next?.contribution||0,delta:(next?.contribution||0)-(f.contribution||0)};
  }).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta));
  const largestRemaining=[...comparisons].sort((a,b)=>b.after-a.after)[0];
  const largestChange=comparisons[0];
  const beforeComponents=new Map((s.before_factors||[]).map(f=>[f.name,f]));
  const afterComponents=new Map((s.after_factors||[]).map(f=>[f.name,f]));
  const excludedIds=s.excluded_transaction_ids||[s.excluded_transaction_id].filter(Boolean);
  const transfer=excludedIds.length===1?state.case?.transactions.find(tx=>tx.transaction_id===excludedIds[0]):null;
  const target=state.stressResultTarget;
  const testedEvidence=target?.mode==='pattern'
    ?`Excluded pattern: <strong>${h(target.label)}</strong> · ${number(excludedIds.length)} transfers`
    :`Excluded transfer: <strong class="mono">${h(excludedIds[0]||'')}</strong>${transfer?` · ${h(transfer.source_account)} → ${h(transfer.destination_account)} · Step ${h(transfer.simulation_step)}`:''}`;
  const delta=value=>`${value>0?'+':''}${decimal(value)} pts`;
  const rows=comparisons.map(f=>`<div class="stress-factor-row ${f.name===largestRemaining?.name?'stress-factor-major':''}"><strong>${h(nameFactor(f.name))}${f.name===largestRemaining?.name?'<span class="stress-major-label">Largest remaining factor</span>':''}</strong><span>${decimal(f.before)} → ${decimal(f.after)} pts</span><span class="stress-factor-delta">${delta(f.delta)}</span></div>`).join('');
  const componentRows=`<div class="stress-factor-breakdown"><div class="section-label">NORMALIZED FACTORS · BEFORE → AFTER</div>${[...beforeComponents.values()].map(f=>`<div class="stress-factor-row"><strong>${h(nameFactor(f.name))}</strong><span>${decimal(f.normalized_value)} → ${decimal(afterComponents.get(f.name)?.normalized_value)}</span></div>`).join('')}</div>`;
  return `<div class="stress-summary"><div class="section-label">PRIORITY SCORE CHANGE</div><div class="stress-tested-evidence">${s.tested_account?`Selected account: <strong>${h(s.tested_account)}</strong><br>`:''}${testedEvidence}${excludedIds.length>1?`<details class="stress-excluded-list"><summary>View excluded transfer IDs</summary><ul>${excludedIds.map(id=>`<li class="mono">${h(id)}</li>`).join('')}</ul></details>`:''}</div><div class="stress-cols"><div><div class="muted small">BEFORE</div><div class="stress-score">${decimal(s.baseline_score)}</div></div><span class="stress-compare">→</span><div><div class="muted small">AFTER</div><div class="stress-score after">${decimal(s.recomputed_score)}</div></div></div><div class="stress-delta">Change: ${delta(s.score_difference)}</div><div class="stress-factor-breakdown"><div class="section-label">FACTOR CONTRIBUTIONS AFTER MODIFIERS · BEFORE → AFTER</div>${rows}</div>${componentRows}<div class="changed-list"><strong>Largest factor change:</strong> ${largestChange?`${h(nameFactor(largestChange.name))} (${delta(largestChange.delta)})`:'No factor change'}<br><strong>Affected alerts:</strong> ${number(s.affected_alert_ids?.length||0)}<br><strong>Case membership:</strong> unchanged</div></div><p class="stress-intro">${h(s.note)}</p>`;
}
async function runStress(){
  const c=state.case;
  const alert=c?.alerts.find(item=>item.alert_id===state.stressAlertId);
  const transactionIds=state.stressMode==='pattern'?Array.from(new Set(alert?.transaction_ids||[])):[state.stressTx].filter(Boolean);
  if(!c||!transactionIds.length||state.stressLoading)return;
  const id=c.case_id,account=state.stressMode==='transaction'?state.focusedAccount:null,token=++state.stressToken;
  const target={mode:state.stressMode,label:alert?`${nameDetector(alert.detector)} · ${alert.alert_id}`:'Individual transaction'};
  state.stressLoading=true;state.stressResult=null;renderIntel();
  try{
    const result=await api.stress(id,transactionIds);
    if(!state.case||state.case.case_id!==id||state.stressToken!==token)return;
    state.stressResult={...result,tested_account:account};
    state.stressResultTarget=target;
    if(transactionIds.length===1){state.selectedTx=transactionIds[0];graph.setSelection(transactionIds[0],account);renderTimeline()}
  }catch(e){if(state.stressToken===token)showError(e.message)}
  finally{
    if(state.stressToken===token){
      state.stressLoading=false;
      if(state.case?.case_id===id&&state.tab==='stress')renderIntel();
    }
  }
}
function debounce(fn,ms){let timer;return (...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),ms)}}
async function openDataset(){$('#dataset-modal').classList.remove('hidden');$('#upload-message').textContent='';try{const status=await api.dataset();$('#dataset-status').textContent=JSON.stringify(status,null,2);state.staged=!!status.pending_upload;$('#analyze-button').disabled=!state.staged;}catch(e){$('#dataset-status').textContent=e.message}}
function closeDataset(){$('#dataset-modal').classList.add('hidden')}
async function stageArchive(ev){ev.preventDefault();const file=$('#archive-file').files[0];if(!file)return;const name=file.name.toLowerCase();if(!name.endsWith('.tgz')&&!name.endsWith('.tar.gz')){showError('Use an IBM .tgz or .tar.gz archive.');return}if(file.size>10*1024*1024){showError('Maximum supported archive size is 10 MiB.');return}
 $('#upload-button').disabled=true;$('#upload-message').textContent='Validating and staging original archive…';try{const staged=await api.stage(file);state.staged=true;$('#analyze-button').disabled=false;$('#upload-message').textContent='Archive staged. Click Analyze staged archive to activate its new case set.';$('#dataset-status').textContent=JSON.stringify(staged,null,2)}catch(e){showError(e.message);$('#upload-message').textContent=e.message}finally{$('#upload-button').disabled=false}}
async function analyze(){if(!state.staged||state.loadingAnalysis)return;state.loadingAnalysis=true;$('#analyze-button').disabled=true;$('#upload-message').textContent='Running analysis. Existing cases remain available until successful completion…';try{await api.analyze();state.staged=false;$('#upload-message').textContent='Analysis complete. The active run has changed.';closeDataset();state.selectedId=null;state.case=null;state.selectedTx=null;state.stressResult=null;state.focusedAccount=null;state.offset=0;location.hash='overview';await bootstrap()}catch(e){showError(e.message);$('#upload-message').textContent=e.message}finally{state.loadingAnalysis=false;$('#analyze-button').disabled=!state.staged}}

bind('#refresh-all','click',bootstrap);bind('#retry','click',bootstrap);bind('#dismiss-error','click',hideError);
bind('#prev-page','click',()=>{state.offset=Math.max(0,state.offset-pageLimit);loadCases()});
bind('#next-page','click',()=>{if(state.offset+pageLimit<state.total){state.offset+=pageLimit;loadCases()}});
bind('#search','input',debounce(ev=>{state.query=ev.target.value.trim();state.offset=0;loadCases()},260));
bind('#detector','change',ev=>{state.detector=ev.target.value;state.offset=0;loadCases()});
bind('#min-priority','change',ev=>{state.minPriority=Number(ev.target.value);state.offset=0;loadCases()});
bind('#review-status','change',ev=>{state.reviewStatus=ev.target.value;state.offset=0;loadCases()});
$$('[data-review-filter]').forEach(button=>button.addEventListener('click',()=>{state.reviewStatus=button.dataset.reviewFilter;$('#review-status').value=state.reviewStatus;state.offset=0;location.hash='reviews';loadCases()}));
bind('#case-review-status','change',ev=>{if(state.case)updateReviewStatus(state.case.case_id,ev.target.value)});
bind('#clear-focus','click',clearEvidenceFilter);
bind('#zoom-in','click',()=>graph.changeZoom(1.24));bind('#zoom-out','click',()=>graph.changeZoom(1/1.24));bind('#zoom-reset','click',()=>graph.reset());
$$('.tab').forEach(button=>button.addEventListener('click',()=>setTab(button.dataset.tab)));
bind('#open-dataset','click',openDataset);bind('#close-dataset','click',closeDataset);
bind('#dataset-modal','click',ev=>{if(ev.target.id==='dataset-modal')closeDataset()});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeDataset()});
bind('#archive-file','change',ev=>$('#file-name').textContent=ev.target.files[0]?.name||'Choose IBM archive');
bind('#upload-form','submit',stageArchive);bind('#analyze-button','click',analyze);
window.addEventListener('hashchange',route);
bootstrap();
