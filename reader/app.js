'use strict';
const DATA = JSON.parse(document.getElementById('library-data').textContent);
const $ = id => document.getElementById(id);
const all = [...DATA.docs, ...DATA.translations];
const byId = new Map(all.map(d => [d.id, d]));
let book = DATA.books[0], current = null, query = '', marks = [], markIndex = -1, searchTimer, scrollTimer;
let restoring = false;
const storeKey = 'yuwen-reader-v3';
function readState(){try{return JSON.parse(localStorage.getItem(storeKey)||'{}')||{};}catch{return {};}}
function saveState(){try{localStorage.setItem(storeKey,JSON.stringify({id:current?.id,scroll:window.scrollY,font:$('font').value,book}));}catch{/* file:// storage may be disabled */}}
function normal(s){return s.replace(/^\s*\d+(?:[.．]\d+)*[.．、]?\s*/,'').replace(/[\s《》〈〉“”"'（）()·：:，,。]/g,'').toLowerCase();}
function words(){return query.toLowerCase().split(/\s+/).filter(Boolean);}
function openSide(){ $('side').hidden=false;$('mask').hidden=false;document.body.classList.add('drawer-open');$('menu').setAttribute('aria-expanded','true');$('search').focus(); }
function closeSide(){ $('side').hidden=true;$('mask').hidden=true;document.body.classList.remove('drawer-open');$('menu').setAttribute('aria-expanded','false');$('menu').focus(); }
function button(text, click, className=''){const b=document.createElement('button');b.type='button';b.textContent=text;b.className=className;b.onclick=click;return b;}
function addHighlighted(el, text, tokens){
  const ranges=[];const lower=text.toLowerCase();
  for(const token of tokens){let pos=0;while((pos=lower.indexOf(token,pos))>=0){ranges.push([pos,pos+token.length]);pos+=token.length;}}
  ranges.sort((a,b)=>a[0]-b[0]);const merged=[];
  for(const r of ranges){const last=merged[merged.length-1];if(last&&r[0]<=last[1])last[1]=Math.max(last[1],r[1]);else merged.push(r);}
  let pos=0;for(const [a,b] of merged){el.append(document.createTextNode(text.slice(pos,a)));const m=document.createElement('mark');m.textContent=text.slice(a,b);el.append(m);pos=b;}el.append(document.createTextNode(text.slice(pos)));
}
function excerpt(d){const tokens=words(),lower=d.content.toLowerCase();const hits=tokens.map(w=>lower.indexOf(w)).filter(p=>p>=0);const pos=hits.length?Math.min(...hits):0;const start=Math.max(0,pos-40);return (start?'…':'')+d.content.slice(start,pos+90).replace(/\n/g,' ')+(pos+90<d.content.length?'…':'');}
function rank(d){const t=normal(d.title),q=normal(query);return t===q?0:t.includes(q)?1:2;}
function renderTree(){
  const box=$('tree');box.replaceChildren();
  document.querySelectorAll('#books button').forEach(b=>{b.classList.toggle('active',b.dataset.book===book);b.setAttribute('aria-pressed',String(b.dataset.book===book));});
  if(query){const tokens=words();const results=DATA.docs.filter(d=>(!$('scope').value||d.book===$('scope').value)&&tokens.every(w=>(d.title+'\n'+d.content).toLowerCase().includes(w))).sort((a,b)=>rank(a)-rank(b));
    $('count').textContent=`命中 ${results.length} 条`;
    for(const d of results){const b=button('',()=>showDoc(d.id,{highlight:true}), 'doc');addHighlighted(b,`[${d.book}] ${d.unit} › ${d.title}`,tokens);const s=document.createElement('small');addHighlighted(s,excerpt(d),tokens);b.append(s);box.append(b);}return;
  }
  $('count').textContent='展开单元，选择课文或栏目';
  const rows=DATA.docs.filter(d=>d.book===book&&d.depth>=2);const groups=new Map();
  for(const d of rows){if(!groups.has(d.unit))groups.set(d.unit,[]);groups.get(d.unit).push(d);}
  for(const [unit,docs] of groups){const group=document.createElement('details');group.open=current?.book===book&&current?.unit===unit;const summary=document.createElement('summary');summary.textContent=unit;group.append(summary);let lastSection=null;
    for(const d of docs){if(!d.content)continue;if(d.section!==lastSection){const h=document.createElement('h3');h.textContent=d.section||'单元说明';group.append(h);lastSection=d.section;}const b=button(d.title,()=>showDoc(d.id),'doc');b.dataset.id=d.id;if(current?.id===d.id)b.setAttribute('aria-current','page');group.append(b);}box.append(group);
  }
}
function goMatch(delta){if(!marks.length)return;markIndex=(markIndex+delta+marks.length)%marks.length;marks.forEach((m,i)=>m.classList.toggle('current',i===markIndex));$('match-count').textContent=`命中 ${markIndex+1} / ${marks.length}`;marks[markIndex].scrollIntoView({block:'center',behavior:'auto'});}
function showDoc(id,{highlight=false,restoreScroll=null}={}){
  const d=byId.get(id);if(!d)return;current=d;book=d.book;closeSide();$('welcome').hidden=true;
  $('title').textContent=d.translation_id?`《${d.title}》参考译文`:d.title;$('crumbs').textContent=d.book+' › '+d.path.split('/').slice(1).join(' › ');
  $('source').textContent=d.subsection?`${d.subsection} · 原文第 ${d.start_line}–${d.end_line} 行`:`出处：${d.book} · ${d.unit} · ${d.section||d.title}`;
  $('source').title=`来源节点：${d.doc_id}`;
  const links=$('links');links.replaceChildren();const labels={translations:'参考译文',tasks:'单元任务',materials:'相关资料',source:'查看原文位置'};
  for(const [kind,ids] of Object.entries(d.links||{})){for(const target of ids){const other=byId.get(target);if(other)links.append(button(labels[kind]+(ids.length>1?' · '+other.title:''),()=>{showDoc(target);if(kind==='source'&&d.start_line){document.querySelector(`[data-line="${d.start_line}"]`)?.scrollIntoView({block:'center'});}}));}}
  if(d.path.includes('/课文解说/')&&!(d.links.translations||[]).length){const note=document.createElement('small');note.textContent='本库未定位到对应参考译文';links.append(note);}
  const content=$('content');content.replaceChildren();$('toc').replaceChildren();const toc=document.createElement('details'),summary=document.createElement('summary');summary.textContent='本节目录';toc.append(summary);let heads=0;
  d.content.split('\n').forEach((line,i)=>{if(!line.trim())return;const isHeading=line.length<=80&&/^(?:[一二三四五六七八九十]+[、.．]|\d+[.、．]|[（(][一二三四五六七八九十]+[）)]|《.*》.*译文)/.test(line);const el=document.createElement(line==='---'?'hr':isHeading?'h2':'p');el.dataset.line=String(i+1);el.id='line-'+(i+1);addHighlighted(el,line,highlight?words():[]);content.append(el);if(isHeading){heads++;const a=document.createElement('a');a.textContent=line;a.href='#'+el.id;a.onclick=e=>{e.preventDefault();el.scrollIntoView({block:'start'});};toc.append(a);}});
  if(heads)$('toc').append(toc);marks=[...content.querySelectorAll('mark')];markIndex=-1;$('matches').hidden=!marks.length;renderTree();
  restoring=restoreScroll!==null;
  if(restoreScroll!==null)requestAnimationFrame(()=>{window.scrollTo(0,restoreScroll);restoring=false;});else if(marks.length)goMatch(1);else window.scrollTo(0,0);
  if(!restoring)saveState();
}
for(const b of DATA.books){const tab=button(b.replace('选择性必修','选必'),()=>{book=b;query='';$('search').value='';renderTree();});tab.dataset.book=b;$('books').append(tab);const option=document.createElement('option');option.value=b;option.textContent=b;$('scope').append(option);}
$('menu').onclick=openSide;$('close').onclick=closeSide;$('mask').onclick=closeSide;
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('side').hidden)closeSide();if(e.key==='Tab'&&!$('side').hidden){const focusable=[...$('side').querySelectorAll('button,input,select,summary')].filter(x=>x.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
function doSearch(){clearTimeout(searchTimer);query=$('search').value.trim();renderTree();}
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(doSearch,150);});$('search').addEventListener('keydown',e=>{if(e.key==='Enter')doSearch();});$('scope').onchange=doSearch;
$('previous').onclick=()=>goMatch(-1);$('next').onclick=()=>goMatch(1);
$('font').onchange=()=>{document.documentElement.style.setProperty('--font',$('font').value+'px');saveState();};
window.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(()=>{if(!restoring)saveState();},180);});window.addEventListener('pagehide',saveState);
const saved=readState();if(['16','18','21'].includes(saved.font)){$('font').value=saved.font;document.documentElement.style.setProperty('--font',saved.font+'px');}if(DATA.books.includes(saved.book))book=saved.book;renderTree();if(saved.id&&byId.has(saved.id))showDoc(saved.id,{restoreScroll:Number(saved.scroll)||0});
