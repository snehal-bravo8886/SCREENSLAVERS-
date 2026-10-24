// Accessible SVG directed multigraph: one edge per source transaction.
// No external graph package, no screenshots or illustrative transactions.
const NS = 'http://www.w3.org/2000/svg';
const el = (tag,attrs={})=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
const clamp=(x,min,max)=>Math.max(min,Math.min(max,x));
function deterministicHash(s){let h=2166136261;for(const c of String(s)){h=Math.imul(h^c.charCodeAt(0),16777619)}return h>>>0}
export function layout(nodes, edges){
  const w=800,h=405, margin=46, n=nodes.length;
  const positions=new Map();
  const degree=new Map(nodes.map(a=>[a.id,0]));
  for(const e of edges){degree.set(e.source,(degree.get(e.source)||0)+1);degree.set(e.target,(degree.get(e.target)||0)+1)}
  const sorted=[...nodes].sort((a,b)=>(degree.get(b.id)-degree.get(a.id))||a.id.localeCompare(b.id));
  sorted.forEach((a,i)=>{
    const angle=2*Math.PI*(i/Math.max(1,n))+((deterministicHash(a.id)%51)-25)/240;
    const ring=(i%4)/3, radius=Math.min(w,h)*(.21+.22*ring);
    positions.set(a.id,{id:a.id,x:w/2+Math.cos(angle)*radius*1.48,y:h/2+Math.sin(angle)*radius,dx:0,dy:0,degree:degree.get(a.id)});
  });
  // Bounded, deterministic force-directed layout; comfortably handles case-sized graphs.
  for(let iter=0;iter<170;iter++){
    const arr=[...positions.values()];
    for(const p of arr){p.dx=(w/2-p.x)*.003;p.dy=(h/2-p.y)*.003}
    for(let i=0;i<arr.length;i++)for(let j=i+1;j<arr.length;j++){
      const a=arr[i],b=arr[j],x=a.x-b.x,y=a.y-b.y,d2=x*x+y*y+70;
      const d=Math.sqrt(d2), force=2200/d2;
      a.dx+=x/d*force;b.dx-=x/d*force;
      a.dy+=y/d*force;b.dy-=y/d*force;
    }
    for(const e of edges){const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b||a===b)continue;
      const x=b.x-a.x,y=b.y-a.y,d=Math.sqrt(x*x+y*y)+.001;
      const force=(d-114)*.012;
      a.dx+=x/d*force;b.dx-=x/d*force;a.dy+=y/d*force;b.dy-=y/d*force;
    }
    const step=iter<95?2.7:1.25;
    for(const p of arr){p.x=clamp(p.x+clamp(p.dx,-8,8)*step,margin,w-margin);p.y=clamp(p.y+clamp(p.dy,-8,8)*step,margin,h-margin)}
  }
  return positions;
}
export class TransactionGraph{
  constructor(container,{onAccount,onTransaction}={}){this.container=container;this.onAccount=onAccount;this.onTransaction=onTransaction;this.focus=null;this.selected=null;this.zoom=1;this.center={x:400,y:202.5};this.model=null;this.draw();}
  setData(graph){this.model=graph;this.focus=null;this.selected=null;this.zoom=1;this.center={x:400,y:202.5};this.draw()}
  setSelection(txid,account){this.selected=txid||null;this.focus=account||null;this.applyStyles()}
  changeZoom(multiplier){this.zoom=clamp(this.zoom*multiplier,.65,3.2);this.adjustView()}
  reset(){this.zoom=1;this.center={x:400,y:202.5};this.adjustView()}
  adjustView(){if(!this.svg)return;const w=800/this.zoom,h=405/this.zoom;this.svg.setAttribute('viewBox',`${this.center.x-w/2} ${this.center.y-h/2} ${w} ${h}`)}
  draw(){this.container.textContent='';this.svg=null;if(!this.model?.nodes?.length){const div=document.createElement('div');div.className='loading-placeholder';div.textContent='No graph available for this case';this.container.append(div);return}
    const graph=this.model,pos=layout(graph.nodes,graph.edges);
    const svg=el('svg',{viewBox:'0 0 800 405',class:'network-svg',role:'group','aria-label':`Directed transaction graph with ${graph.nodes.length} accounts and ${graph.edges.length} transfers. Select a node or edge to inspect evidence.`});
    const defs=el('defs'); const mark=el('marker',{id:'graph-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:4.5,markerHeight:4.5,orient:'auto-start-reverse'});mark.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#88a1b5'}));defs.append(mark);
    const markSelect=el('marker',{id:'graph-arrow-select',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:4.5,markerHeight:4.5,orient:'auto'});markSelect.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#ff9865'}));defs.append(markSelect);svg.append(defs);
    const links=el('g',{'aria-label':'Transactions'}),nodes=el('g',{'aria-label':'Accounts'});
    const pairCounts=new Map(),pairIndex=new Map();
    graph.edges.forEach(e=>{const k=[e.source,e.target].sort().join('|');pairCounts.set(k,(pairCounts.get(k)||0)+1)});
    for(const e of graph.edges){const a=pos.get(e.source),b=pos.get(e.target);if(!a||!b)continue;
      const key=[e.source,e.target].sort().join('|'),i=pairIndex.get(key)||0;pairIndex.set(key,i+1);
      const count=pairCounts.get(key),dir=a.id.localeCompare(b.id)<0?1:-1;
      const offset=(i-(count-1)/2)*14*dir;
      const dx=b.x-a.x,dy=b.y-a.y,l=Math.max(Math.hypot(dx,dy),1),nx=-dy/l,ny=dx/l;
      let d;
      if(a===b||l<4) d=`M ${a.x-10} ${a.y-8} C ${a.x-40} ${a.y-48},${a.x+37} ${a.y-46},${a.x+14} ${a.y-8}`;
      else{
        const startX=a.x+dx/l*15,startY=a.y+dy/l*15,endX=b.x-dx/l*17,endY=b.y-dy/l*17;
        d=`M ${startX.toFixed(2)} ${startY.toFixed(2)} Q ${((a.x+b.x)/2+nx*offset).toFixed(2)} ${((a.y+b.y)/2+ny*offset).toFixed(2)} ${endX.toFixed(2)} ${endY.toFixed(2)}`;
      }
      const path=el('path',{d,class:'network-edge','data-txid':e.transaction_id,'marker-end':'url(#graph-arrow)',tabindex:0,role:'button','aria-label':`Transfer ${e.transaction_id}, ${e.source} to ${e.target}, amount ${e.amount}, simulation step ${e.simulation_step}`});
      const title=el('title');title.textContent=`${e.source} → ${e.target} · ${e.amount} units · Step ${e.simulation_step} · ${e.transaction_id}`;path.append(title);
      const hit=el('path',{d,class:'edge-hit','data-txid':e.transaction_id,tabindex:-1});
      const select=()=>this.onTransaction?.(e.transaction_id);
      path.addEventListener('click',select);hit.addEventListener('click',select);path.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();select()}});
      links.append(path,hit);
    }
    for(const p of pos.values()){
      const g=el('g',{class:'network-node','data-account':p.id,role:'button',tabindex:0,'aria-label':`Account ${p.id}, click to filter its transfers`});
      const circle=el('circle',{cx:p.x,cy:p.y,r:14,class:'node-circle'}),text=el('text',{x:p.x,y:p.y,class:'node-label'});text.textContent=p.id;
      const title=el('title');title.textContent=`Account ${p.id} · ${p.degree} transfer endpoints`;
      g.append(circle,text,title);
      const select=()=>this.onAccount?.(p.id);
      g.addEventListener('click',select);g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();select()}});
      nodes.append(g);
    }
    svg.append(links,nodes);this.container.append(svg);this.svg=svg;
    let drag=null;
    svg.addEventListener('pointerdown',ev=>{if(ev.target.closest('[data-account],[data-txid]'))return;drag={x:ev.clientX,y:ev.clientY,baseX:this.center.x,baseY:this.center.y};svg.setPointerCapture(ev.pointerId)});
    svg.addEventListener('pointermove',ev=>{if(!drag)return;const box=svg.getBoundingClientRect();this.center={x:drag.baseX-(ev.clientX-drag.x)*(800/this.zoom/Math.max(box.width,1)),y:drag.baseY-(ev.clientY-drag.y)*(405/this.zoom/Math.max(box.height,1))};this.adjustView()});
    svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);
    svg.addEventListener('wheel',ev=>{ev.preventDefault();this.changeZoom(ev.deltaY<0?1.10:1/1.10)},{passive:false});
    this.applyStyles();
  }
  applyStyles(){if(!this.svg||!this.model)return;
    const connected=new Set(this.model.edges.filter(e=>e.source===this.focus||e.target===this.focus).map(e=>e.transaction_id));
    for(const edge of this.svg.querySelectorAll('.network-edge')){
      const id=edge.dataset.txid, selected=id===this.selected;
      edge.classList.toggle('selected',selected);edge.classList.toggle('faded',!!this.focus&&!connected.has(id));
      edge.setAttribute('marker-end',selected?'url(#graph-arrow-select)':'url(#graph-arrow)');
    }
    for(const g of this.svg.querySelectorAll('.network-node')){
      const id=g.dataset.account,focus=id===this.focus,neighbor=!!this.focus&&this.model.edges.some(e=>(e.source===id&&e.target===this.focus)||(e.target===id&&e.source===this.focus));
      g.classList.toggle('focus',focus);g.classList.toggle('neighbor',neighbor);g.classList.toggle('faded',!!this.focus&&!focus&&!neighbor);
    }
  }
}
