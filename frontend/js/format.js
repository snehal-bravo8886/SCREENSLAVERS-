export const $ = (selector,base=document)=>base.querySelector(selector);
export const $$ = (selector,base=document)=>Array.from(base.querySelectorAll(selector));
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number = value => Number(value ?? 0).toLocaleString('en-IN',{maximumFractionDigits:2});
export const decimal = value => Number(value ?? 0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
export const shortId = value => String(value||'').replace(/^CASE-/,'');
export const nameDetector = kind => ({fan_in:'Fan-in',fan_out:'Fan-out',rapid_pass_through:'Rapid flow',temporal_cycle:'Cycle'})[kind] || kind;
export const nameFactor = kind => ({pattern_strength:'Pattern strength (M)',activity_anomaly:'Account activity anomaly (A)',evidence_support:'Evidence support (C)'})[kind] || kind;
export const explainDetector = kind => ({
  fan_in:'Several accounts send transfers to the same destination.',
  fan_out:'One account sends transfers to several recipients.',
  rapid_pass_through:'Connected accounts pass funds onward over a short sequence of simulation steps.',
  temporal_cycle:'Transfers form a loop that returns to an earlier account over increasing simulation steps.'
})[kind] || 'This detector matched a configured transaction-pattern rule.';
export const stepRange = item => item?.start_step === item?.end_step ? `Step ${item?.start_step ?? '—'}` : `Steps ${item?.start_step ?? '—'}–${item?.end_step ?? '—'}`;
export const evidenceAmount = amount => `${decimal(amount)} units`;
