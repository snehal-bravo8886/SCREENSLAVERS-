import {api,BASE_API} from './api.js';
import {TransactionGraph} from './graph.js';
import {$,$$,escapeHTML as h,number,decimal,nameDetector,nameFactor,stepRange,shortId} from './format.js';

const pageLimit=15;
const state={summary:null,queue:[],total:0,offset:0,selectedId:null,case:null,tab:'evidence',selectedTx:null,focusedAccount:null,stressTx:null,stressResult:null,stressLoading:false,query:'',detector:'',minPriority:0,queueToken:0,caseToken:0,online:false,staged:false,loadingAnalysis:false};
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
    state.summary=summary;setConnection(true);renderSummary();state.offset=0;await loadCases(true);
  }catch(e){setConnection(false);showError(e.message);if(!state.case){empty($('#case-list'),'Backend unavailable','Start Uvicorn on port 8000 and click Retry.');loading($('#graph-surface'),'Waiting for backend');empty($('#timeline'),'No transaction data','');empty($('#intel-content'),'No investigation selected','')}}
}
function renderSummary(){const s=state.summary;if(!s)return;
  $('#stat-transactions').textContent=number(s.transactions??s.input_transactions);
  $('#stat-alerts').textContent=number(s.alerts??s.input_alerts);
  $('#stat-cases').textContent=number(s.cases);
  $('#run-id').textContent=s.run_id||'UNKNOWN';
}
async function loadCases(autoselect=false){const token=++state.queueToken;loading($('#case-list'),'Retrieving prioritized cases…');
  try{const response=await api.cases({limit:pageLimit,offset:state.offset,minPriority:state.minPriority,detector:state.detector,search:state.query});if(token!==state.queueToken)return;
    if(state.summary && response.run_id!==state.summary.run_id){await bootstrap();return}
    state.queue=response.items;state.total=response.total;renderQueue();
    if(autoselect || !state.selectedId){if(response.items[0])await selectCase(response.items[0].case_id);else clearCase()}
  }catch(e){if(token!==state.queueToken)return;showError(e.message);empty($('#case-list'),'Could not load cases',e.message)}
}
function renderQueue(){$('#queue-total').textContent=number(state.total);
  const list=$('#case-list');
  if(!state.queue.length){empty(list,'No matching cases','Try another search, detector or priority threshold.');}
  else{list.innerHTML=state.queue.map((c,i)=>`<button type="button" class="case-item ${state.selectedId===c.case_id?'selected':''}" data-case-id="${h(c.case_id)}" aria-pressed="${state.selectedId===c.case_id}"><div class="case-item-top"><span class="case-rank">${String(state.offset+i+1).padStart(2,'0')}</span><span class="case-id">${h(shortId(c.case_id))}</span><span class="case-score">${decimal(c.priority_score).replace('.00','')}</span></div><div class="case-tagline">${h(c.detector_types.map(nameDetector).join(' · '))}</div><div class="case-mini"><span>${number(c.alert_count)} alerts</span><span>${number(c.evidence_count)} transfers</span><span>${h(stepRange(c))}</span></div></button>`).join('');
    $$('.case-item',list).forEach(item=>item.addEventListener('click',()=>selectCase(item.dataset.caseId)));
  }
  $('#pagination-label').textContent=state.total?`${number(state.offset+1)}–${number(Math.min(state.offset+pageLimit,state.total))} of ${number(state.total)}`:'0 results';
  $('#prev-page').disabled=state.offset===0;$('#next-page').disabled=state.offset+pageLimit>=state.total;
}
function clearCase(){state.selectedId=null;state.case=null;state.selectedTx=null;state.focusedAccount=null;state.stressResult=null;graph.setData(null);
  $('#selected-case-title').textContent='Transaction network';$('#selected-case-meta').textContent='Select a case to inspect source evidence';$('#priority-score').textContent='—';$('#timeline-counter').textContent='—';empty($('#intel-content'),'No case selected','Select a case from the queue');empty($('#timeline'),'No transfers to show','');}
async function selectCase(id){if(!id)return;state.selectedId=id;state.case=null;state.stressResult=null;state.selectedTx=null;state.focusedAccount=null;state.stressTx=null;const token=++state.caseToken;renderQueue();
  $('#selected-case-title').textContent=`Case ${shortId(id)}`;
  $('#selected-case-meta').textContent='Loading verified case evidence…';loading($('#graph-surface'),'Building directed transaction graph…');loading($('#timeline'),'Loading timeline…');loading($('#intel-content'),'Retrieving risk factors and alerts…');
  try{const detail=await api.case(id);if(token!==state.caseToken)return;
    if(detail.case_id!==id || detail.time_unit!=='simulation_step' ||detail.score_is_probability!==false)throw new Error('Case detail violates the agreed backend contract');
    state.case=detail;
    state.stressTx=detail.transactions?.[0]?.transaction_id||null;
    graph.setData(detail.graph);
    $('#selected-case-meta').textContent=`${number(detail.account_ids.length)} accounts  ·  ${number(detail.evidence_count)} transactions  ·  ${stepRange(detail)}`;
    $('#priority-score').textContent=decimal(detail.priority_score);
    $('#graph-size').textContent=`${detail.graph.nodes.length} nodes · ${detail.graph.edges.length} edges`;
    renderTimeline();renderIntel();
  }catch(e){if(token!==state.caseToken)return;showError(e.message);empty($('#graph-surface'),'Case unavailable',e.message);empty($('#intel-content'),'Could not load this case',e.message)}
}
function selectAccount(account){if(!state.case)return;state.focusedAccount=state.focusedAccount===account?null:account;state.selectedTx=null;graph.setSelection(null,state.focusedAccount);renderTimeline();renderIntel();}
function selectTransaction(txid){if(!state.case)return;state.selectedTx=txid;state.stressTx=txid;graph.setSelection(txid,state.focusedAccount);renderTimeline();renderIntel();}
function renderTimeline(){const c=state.case;if(!c){empty($('#timeline'),'No timeline','');return}
 const txs=[...c.transactions].sort((a,b)=>a.simulation_step-b.simulation_step||a.transaction_id.localeCompare(b.transaction_id));
 const filtered=state.focusedAccount?txs.filter(t=>t.source_account===state.focusedAccount||t.destination_account===state.focusedAccount):txs;
 $('#timeline-counter').textContent=`${number(filtered.length)} of ${number(txs.length)} transfers`;
 $('#focus-description').textContent=state.focusedAccount?`Showing transfers touching account ${state.focusedAccount}`:'Click a graph node or edge to inspect evidence';
 $('#clear-focus').classList.toggle('hidden',!state.focusedAccount);
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
   if(selected){html+=`<div class="section-label">SELECTED EVIDENCE</div><div class="evidence-highlight"><strong class="mono">${h(selected.transaction_id)}</strong><p>${h(selected.source_account)} → ${h(selected.destination_account)}<br>Amount: ${decimal(selected.amount)} synthetic units · Step ${h(selected.simulation_step)}</p><button type="button" id="stress-selected" class="btn btn-small">Stress-test this transfer →</button></div>`}
   html+=`<div class="section-label">WHY THIS CASE IS FLAGGED</div><div class="signal-list">${c.alerts.map(a=>`<button type="button" class="signal selectable-alert" data-alert="${h(a.alert_id)}"><div class="signal-head"><span class="signal-label">${h(nameDetector(a.detector))}</span><span class="signal-badge">${number(a.transaction_ids.length)} transfers</span></div><p class="signal-reason">${h(a.reason||'Transaction pattern met the configured rule threshold.')}</p><div class="signal-evidence mono">${h(a.alert_id)} · ${h(stepRange(a))}</div></button>`).join('')}</div>`;
   content.innerHTML=html;
   $('#stress-selected')?.addEventListener('click',()=>{state.stressTx=state.selectedTx;setTab('stress')});
   $$('.selectable-alert',content).forEach(b=>b.addEventListener('click',()=>{const alert=c.alerts.find(a=>a.alert_id===b.dataset.alert);if(alert?.transaction_ids?.length){state.focusedAccount=null;selectTransaction(alert.transaction_ids[0])}}));
 }else if(state.tab==='factors'){
   content.innerHTML=`<div class="section-label">EXPLAINABLE PRIORITY FACTORS</div><p class="stress-intro">A transparent weighted 0–100 review-priority index, not calibrated fraud likelihood. Unavailable history is reweighted by the scoring engine.</p>${factorMarkup(c.risk_factors)}<div class="section-label">CASE ASSESSMENT</div><p class="stress-intro">${h(c.indicator_notes||'These rule indicators share some evidence and should not be treated as independent probabilities.')}</p>`;
 }else{
   let options=c.transactions.map(t=>`<option value="${h(t.transaction_id)}" ${state.stressTx===t.transaction_id?'selected':''}>Step ${h(t.simulation_step)} · ${h(t.source_account)} → ${h(t.destination_account)} · ${decimal(t.amount)} units · ${h(t.transaction_id)}</option>`).join('');
   content.innerHTML=`<div class="section-label">COUNTERFACTUAL EVIDENCE REVIEW</div><p class="stress-intro">Temporarily exclude one source transfer and recalculate risk-factor contributions. Original evidence and case membership remain unchanged.</p><label for="stress-transaction" class="stress-label">Evidence transaction to exclude</label><select id="stress-transaction" class="stress-picker">${options}</select><div class="stress-actions"><button type="button" id="run-stress" class="btn btn-primary" ${state.stressLoading?'disabled':''}>${state.stressLoading?'Recalculating…':'Run Stress Test'}</button><button type="button" id="reset-stress" class="btn btn-secondary" ${state.stressResult?'':'disabled'}>Reset</button></div><div id="stress-output">${state.stressResult?stressMarkup(state.stressResult):'<div class="empty-state"><strong>Ready to challenge the evidence</strong>Choose any transaction from this case and recalculate its priority index.</div>'}</div>`;
   $('#stress-transaction').addEventListener('change',ev=>{state.stressTx=ev.target.value;state.stressResult=null;renderIntel()});
   $('#run-stress').addEventListener('click',runStress);
   $('#reset-stress').addEventListener('click',()=>{state.stressResult=null;state.stressTx=c.transactions[0]?.transaction_id||null;renderIntel()});
 }
}
function factorMarkup(factors){return factors.map(f=>{const pct=f.available?Math.round(100*(f.normalized_value||0)):0;return `<div class="factor"><div class="factor-head"><strong>${h(nameFactor(f.name))}</strong>${f.available?`<span>${decimal(f.contribution)} pts</span>`:'<span class="unavailable">History unavailable</span>'}</div><div class="factor-sub"><span>Weight: ${(Number(f.weight)*100).toFixed(0)}%${f.available?'':' (excluded)'}</span><span>${f.available?`${pct}% signal`:'no measurement'}</span></div><div class="factor-track"><div class="factor-fill" style="width:${pct}%"></div></div><p class="description">${h(f.description)}</p></div>`}).join('')}
function stressMarkup(s){const changed=s.changed_factors||[];return `<div class="stress-summary"><div class="section-label">RECOMPUTED PRIORITY</div><div class="stress-cols"><div><div class="muted small">BEFORE</div><div class="stress-score">${decimal(s.baseline_score)}</div></div><span class="stress-compare">→</span><div><div class="muted small">AFTER</div><div class="stress-score after">${decimal(s.recomputed_score)}</div></div></div><div class="stress-delta">Change: ${s.score_difference>0?'+':''}${decimal(s.score_difference)} points</div><div class="changed-list"><strong>Changed factors:</strong> ${changed.length?changed.map(nameFactor).map(h).join(', '):'No change'}<br><strong>Affected alerts:</strong> ${number(s.affected_alert_ids?.length||0)}<br><strong>Membership recomputed:</strong> ${s.membership_recomputed?'Yes':'No (fixed)'}</div></div><div class="section-label" style="margin-top:20px">AFTER-EXCLUSION FACTORS</div>${factorMarkup(s.after_factors)}<p class="stress-intro">${h(s.note)}</p>`}
async function runStress(){const c=state.case;if(!c||!state.stressTx||state.stressLoading)return;const id=c.case_id,tx=state.stressTx;state.stressLoading=true;state.stressResult=null;renderIntel();try{const result=await api.stress(id,tx);if(!state.case||state.case.case_id!==id)return;state.stressResult=result;state.selectedTx=tx;graph.setSelection(tx,state.focusedAccount);renderTimeline();}catch(e){showError(e.message)}finally{state.stressLoading=false;if(state.case?.case_id===id&&state.tab==='stress')renderIntel()}}
function debounce(fn,ms){let timer;return (...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),ms)}}
async function openDataset(){$('#dataset-modal').classList.remove('hidden');$('#upload-message').textContent='';try{const status=await api.dataset();$('#dataset-status').textContent=JSON.stringify(status,null,2);state.staged=!!status.pending_upload;$('#analyze-button').disabled=!state.staged;}catch(e){$('#dataset-status').textContent=e.message}}
function closeDataset(){$('#dataset-modal').classList.add('hidden')}
async function stageArchive(ev){ev.preventDefault();const file=$('#archive-file').files[0];if(!file)return;const name=file.name.toLowerCase();if(!name.endsWith('.tgz')&&!name.endsWith('.tar.gz')){showError('Use an IBM .tgz or .tar.gz archive.');return}if(file.size>10*1024*1024){showError('Maximum supported archive size is 10 MiB.');return}
 $('#upload-button').disabled=true;$('#upload-message').textContent='Validating and staging original archive…';try{const staged=await api.stage(file);state.staged=true;$('#analyze-button').disabled=false;$('#upload-message').textContent='Archive staged. Click Analyze staged archive to activate its new case set.';$('#dataset-status').textContent=JSON.stringify(staged,null,2)}catch(e){showError(e.message);$('#upload-message').textContent=e.message}finally{$('#upload-button').disabled=false}}
async function analyze(){if(!state.staged||state.loadingAnalysis)return;state.loadingAnalysis=true;$('#analyze-button').disabled=true;$('#upload-message').textContent='Running analysis. Existing cases remain available until successful completion…';try{await api.analyze();state.staged=false;$('#upload-message').textContent='Analysis complete. The active run has changed.';closeDataset();state.selectedId=null;state.case=null;state.selectedTx=null;state.stressResult=null;state.focusedAccount=null;state.offset=0;await bootstrap()}catch(e){showError(e.message);$('#upload-message').textContent=e.message}finally{state.loadingAnalysis=false;$('#analyze-button').disabled=!state.staged}}

bind('#refresh-all','click',bootstrap);bind('#retry','click',bootstrap);bind('#dismiss-error','click',hideError);
bind('#prev-page','click',()=>{state.offset=Math.max(0,state.offset-pageLimit);loadCases(false)});
bind('#next-page','click',()=>{if(state.offset+pageLimit<state.total){state.offset+=pageLimit;loadCases(false)}});
bind('#search','input',debounce(ev=>{state.query=ev.target.value.trim();state.offset=0;loadCases(false)},260));
bind('#detector','change',ev=>{state.detector=ev.target.value;state.offset=0;loadCases(false)});
bind('#min-priority','change',ev=>{state.minPriority=Number(ev.target.value);state.offset=0;loadCases(false)});
bind('#clear-focus','click',()=>selectAccount(state.focusedAccount));
bind('#zoom-in','click',()=>graph.changeZoom(1.24));bind('#zoom-out','click',()=>graph.changeZoom(1/1.24));bind('#zoom-reset','click',()=>graph.reset());
$$('.tab').forEach(button=>button.addEventListener('click',()=>setTab(button.dataset.tab)));
bind('#open-dataset','click',openDataset);bind('#close-dataset','click',closeDataset);
bind('#dataset-modal','click',ev=>{if(ev.target.id==='dataset-modal')closeDataset()});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeDataset()});
bind('#archive-file','change',ev=>$('#file-name').textContent=ev.target.files[0]?.name||'Choose IBM archive');
bind('#upload-form','submit',stageArchive);bind('#analyze-button','click',analyze);
bootstrap();
