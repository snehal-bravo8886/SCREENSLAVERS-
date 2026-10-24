// Real HTTP tests against Member 4 backend; run with backend listening on port 8000.
import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.location={hostname:'127.0.0.1',search:''};
const {api}=await import('../js/api.js');
const alive=await api.health().catch(()=>null);
const real=test.skip===undefined?test:test;
real('backend health is loaded and native simulation step units match', {skip:!alive}, async()=>{
  assert.equal(alive.ready,true);assert.equal(alive.time_unit,'simulation_step');
});
real('real dataset and case queue agree with analysis baseline',{skip:!alive},async()=>{
  const [summary,queue]=await Promise.all([api.summary(),api.cases({limit:3})]);
  assert.equal(summary.transactions,120558);assert.equal(summary.alerts,2912);assert.equal(summary.cases,2573);
  assert.equal(queue.items.length,3);assert(queue.items[0].priority_score>=queue.items[1].priority_score);
  assert.equal(queue.total,2573);assert.equal(queue.score_is_probability,false);
});
real('case graph edges and timeline exactly match case evidence',{skip:!alive},async()=>{
  const id='CASE-1086856BCDCD';const [detail,graph,timeline]=await Promise.all([api.case(id),api.graph(id),api.timeline(id)]);
  assert.equal(detail.evidence_count,25);assert.equal(detail.alert_count,7);
  assert.equal(graph.edges.length,25);assert.equal(timeline.items.length,25);
  assert.deepEqual(new Set(graph.edges.map(e=>e.transaction_id)),new Set(detail.transaction_ids));
  assert(graph.edges.every(e=>Number.isInteger(e.simulation_step) && e.currency==='XXX'));
});
real('real stress test returns exact before/after scores without fake data',{skip:!alive},async()=>{
  const before=await api.case('CASE-1086856BCDCD');
  const result=await api.stress('CASE-1086856BCDCD','IBM20K-ROW-0005975');
  assert.equal(result.baseline_score,before.priority_score);
  assert.equal(result.baseline_score_components.priority_score,result.baseline_score);
  assert.equal(result.recomputed_score_components.priority_score,result.recomputed_score);
  assert.equal(result.score_difference,Number((result.recomputed_score-result.baseline_score).toFixed(2)));
  assert.equal(result.membership_recomputed,false);
});
real('search, detector filters, pagination are backend-driven',{skip:!alive},async()=>{
  const cases=await api.cases({detector:'temporal_cycle',limit:10});
  assert(cases.items.every(x=>x.detector_types.includes('temporal_cycle')));
  const missing=await api.cases({search:'NOT_A_REAL_CASE_ID_999',limit:10});
  assert.equal(missing.total,0);
});
