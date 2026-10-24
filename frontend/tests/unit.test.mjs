import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML,decimal,number,nameDetector,stepRange,shortId} from '../js/format.js';
import {layout} from '../js/graph.js';
test('untrusted API strings are HTML escaped before rendering',()=>{
  assert.equal(escapeHTML('<script>"&\'</script>'), '&lt;script&gt;&quot;&amp;&#39;&lt;/script&gt;');
});
test('IBM simulation step range is not converted into a date',()=>{
  assert.equal(stepRange({start_step:23,end_step:29}),'Steps 23–29');
  assert.equal(stepRange({start_step:29,end_step:29}),'Step 29');
});
test('labels distinguish synthetic units and detector types',()=>{
  assert.equal(nameDetector('rapid_pass_through'),'Rapid flow');
  assert.equal(decimal(95.26),'95.26');
  assert.equal(shortId('CASE-ABC'),'ABC');
});
test('graph layout deterministic and finite on real-shape multigraph',()=>{
  const nodes=Array.from({length:25},(_,i)=>({id:String(i)}));
  const edges=Array.from({length:35},(_,i)=>({source:String(i%25),target:String((i*7+1)%25),transaction_id:`T-${i}`}));
  const a=layout(nodes,edges),b=layout(nodes,edges);
  assert.equal(a.size,25);
  for(const node of nodes){assert.deepEqual(a.get(node.id),b.get(node.id));assert(Number.isFinite(a.get(node.id).x));assert(Number.isFinite(a.get(node.id).y))}
});
