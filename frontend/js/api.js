// The one and only data provider. No hardcoded cases, fake transactions, or example scores.
// Use the host on which the UI was opened, with backend port 8000 by default.
const DEFAULT_API = `http://${location.hostname === 'localhost' ? 'localhost' : '127.0.0.1'}:8000`;
export const BASE_API = new URLSearchParams(location.search).get('api') || DEFAULT_API;

export class ApiError extends Error {
  constructor(status, message) { super(message); this.name = 'ApiError'; this.status = status; }
}
async function request(path, init={}) {
  let response;
  try { response = await fetch(`${BASE_API}${path}`, { cache: 'no-store', ...init }); }
  catch { throw new ApiError(0, 'Cannot reach backend at ' + BASE_API + '. Start Uvicorn on port 8000.'); }
  let body;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const detail = body?.error || (typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail || {}));
    throw new ApiError(response.status, `HTTP ${response.status}: ${detail}`);
  }
  return body;
}
export const api = {
  health: () => request('/health'),
  summary: () => request('/api/summary'),
  dataset: () => request('/api/datasets/current'),
  meta: () => request('/api/meta'),
  cases: ({limit=20,offset=0,minPriority=0,detector='',search='',reviewStatus='all'}={}) => {
    const qs = new URLSearchParams({limit:String(limit),offset:String(offset),min_priority:String(minPriority)});
    if(detector) qs.set('detector',detector);
    if(search) qs.set('search',search);
    if(reviewStatus && reviewStatus !== 'all') qs.set('review_status',reviewStatus);
    return request(`/api/cases?${qs}`);
  },
  setReviewStatus: (id,status) => request(`/api/cases/${encodeURIComponent(id)}/review`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})}),
  case: id => request(`/api/cases/${encodeURIComponent(id)}`),
  graph: id => request(`/api/cases/${encodeURIComponent(id)}/graph`),
  timeline: id => request(`/api/cases/${encodeURIComponent(id)}/timeline`),
  transaction: id => request(`/api/transactions/${encodeURIComponent(id)}`),
  alert: id => request(`/api/alerts/${encodeURIComponent(id)}`),
  stress: (id, transactionIds) => {
    const body=Array.isArray(transactionIds)?{excluded_transaction_ids:transactionIds}:{excluded_transaction_id:transactionIds};
    return request(`/api/cases/${encodeURIComponent(id)}/stress-test`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  },
  stage: file => {const form=new FormData();form.append('file',file);return request('/api/datasets/load',{method:'POST',body:form});},
  analyze: () => request('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({include_cycles:true})})
};
