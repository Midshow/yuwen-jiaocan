# -*- coding: utf-8 -*-
"""SQLite 教参库 → 单文件 HTML 查询器 v2（同学可用版）
v2 修复：①目录改抽屉式（按钮点开） ②单元/课文按原始书序 ③册目切换修复
"""
import sqlite3, json, os, html, re, sys

DB = r'C:\Users\Administrator\AppData\Local\hermes\cache\documents\flowus_data\高中语文教参.db'
OUT = r'C:\Users\Administrator\.openclaw\workspace\yuwen-jiaocan-public\yuwen-jiaocan.html'

BOOK_ORDER = ['必修上册', '必修下册', '选择性必修上册', '选择性必修中册', '选择性必修下册']
SECTION_KEYWORDS = {
    '课文解说': '课文解说',
    '关于单元学习任务': '单元学习任务',
    '关于单元研习任务': '单元研习任务',
    '单元教学设计举例': '教学设计',
    '资料链接': '资料链接',
    '目标意图指导': '目标意图',
}
SECTION_ORDER = ['目标意图', '课文解说', '单元学习任务', '单元研习任务', '教学设计', '资料链接', '其他', '编写说明']

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # 按书内原始顺序（ord 是父内序号，DFS 插入保序）
    cur.execute("SELECT book, path, title, content, depth, ord FROM docs ORDER BY book, ord")
    rows = cur.fetchall()

    # 组树（dict 保持插入序 = 书内原始序）
    books = {}
    ke_index = []
    for book, path, title, content, depth, ord_ in rows:
        if depth < 2:
            continue
        parts = [p for p in path.split('/') if p]
        if len(parts) < 2:
            continue
        unit = parts[1] if len(parts) > 1 else '其他'
        section = None
        for kw, label in SECTION_KEYWORDS.items():
            if kw in path or kw in title:
                section = label
                break
        if section is None:
            if '课文解说' in path:
                section = '课文解说'
            elif '编写说明' in path or title == '编写说明':
                section = '编写说明'
            else:
                section = '其他'
        books.setdefault(book, {})
        books[book].setdefault(unit, {})
        books[book][unit].setdefault(section, [])
        books[book][unit][section].append({
            't': title,
            'c': content,
            'p': path,
        })
        if section == '课文解说' and depth >= 4 and content:
            ke_index.append({'book': book, 'title': title, 'n': len(content)})

    # 课文解说索引：按书内顺序（不重排）
    ke_by_book = {}
    for item in ke_index:
        ke_by_book.setdefault(item['book'], []).append(item)

    data = {'books': books, 'ke': ke_by_book, 'book_order': BOOK_ORDER}
    data_json = json.dumps(data, ensure_ascii=False)
    # 防 </script> 提前闭合：JSON 内 '</' 安全转义（JS 字符串等价）
    data_json = data_json.replace('</', '<\\/')
    print(f'节点数: {len(rows)} | JSON: {len(data_json.encode("utf-8"))//1024}KB')

    css = '''
    :root { --c-main:#1f2937; --c-accent:#2563eb; --c-bg:#f8fafc; --c-side:#111827; --c-side-txt:#d1d5db; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif; color:var(--c-main); background:var(--c-bg); }
    #topbar { position:sticky; top:0; z-index:50; display:flex; align-items:center; gap:10px; padding:10px 14px; background:#111827; color:#fff; }
    #topbar h1 { font-size:16px; margin:0; flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    #menu-btn { background:#2563eb; border:none; color:#fff; font-size:14px; padding:8px 14px; border-radius:8px; cursor:pointer; white-space:nowrap; }
    #menu-btn:hover { background:#1d4ed8; }
    #cur-book { font-size:12px; color:#93c5fd; background:#1f2937; padding:4px 10px; border-radius:12px; white-space:nowrap; }
    /* 抽屉 */
    #mask { position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:90; display:none; }
    #side { position:fixed; top:0; left:0; bottom:0; width:min(88vw, 380px); background:var(--c-side); color:var(--c-side-txt); z-index:100; display:flex; flex-direction:column; transform:translateX(-105%); transition:transform .25s ease; box-shadow:4px 0 20px rgba(0,0,0,.3); }
    #side.open { transform:translateX(0); }
    #side-head { padding:12px 14px; border-bottom:1px solid #1f2937; }
    #side-head .row { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
    #side-head .row h2 { font-size:15px; color:#fff; margin:0; flex:1; }
    #close-btn { background:none; border:none; color:#9ca3af; font-size:20px; cursor:pointer; }
    #search { width:100%; padding:8px 10px; border-radius:6px; border:1px solid #374151; background:#1f2937; color:#fff; font-size:14px; }
    #search::placeholder { color:#6b7280; }
    #book-tabs { display:flex; gap:4px; padding:10px 8px 2px; flex-wrap:wrap; }
    .btab { padding:4px 9px; border-radius:14px; font-size:12px; background:#1f2937; color:#9ca3af; cursor:pointer; border:1px solid #374151; }
    .btab.active { background:#2563eb; color:#fff; border-color:#2563eb; }
    #tree { flex:1; overflow-y:auto; padding:6px 6px 24px; font-size:13px; }
    .node { padding:4px 8px; border-radius:4px; cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .node:hover { background:#1f2937; }
    .node.sel { background:#2563eb; color:#fff; }
    .node.unit { color:#fff; font-weight:bold; margin-top:6px; }
    .node.section { color:#93c5fd; font-size:12px; }
    .node.doc { color:#9ca3af; padding-left:18px; }
    .node.empty { color:#4b5563; font-style:italic; cursor:default; }
    #result-count { padding:6px 12px; font-size:12px; color:#f59e0b; }
    .footer { padding:10px 14px; font-size:11px; color:#4b5563; border-top:1px solid #e5e7eb; background:#fff; }
    /* 主区 */
    #main { padding:16px 18px 80px; max-width:900px; margin:0 auto; }
    #crumbs { font-size:12px; color:#6b7280; margin-bottom:8px; word-break:break-all; }
    #title { font-size:22px; color:#1d4ed8; border-bottom:2px solid #2563eb; padding-bottom:8px; margin:0 0 14px; }
    #content { line-height:1.9; font-size:15px; }
    #content p { margin:8px 0; text-align:justify; }
    #content .h { font-weight:bold; color:#b45309; margin:16px 0 6px; }
    #content hr { border:none; border-top:1px dashed #cbd5e1; margin:14px 0; }
    #toc-inner { background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:10px 14px; margin-bottom:16px; }
    .toc-title { font-weight:bold; color:#1d4ed8; margin-bottom:6px; font-size:13px; }
    .toc-item { display:block; color:#2563eb; text-decoration:none; font-size:13px; padding:3px 0; border-bottom:1px dashed #dbeafe; }
    .toc-item:hover { color:#1d4ed8; text-decoration:underline; background:#dbeafe; }
    .h-highlight { animation: hl 2s ease; }
    @keyframes hl { 0%{ background:#fef08a; } 100%{ background:transparent; } }
    #hint { color:#6b7280; text-align:center; margin-top:60px; font-size:15px; }
    #hint b { color:#2563eb; }
    '''

    js = '''
    const DATA = __DATA__;
    const BOOK_ORDER = DATA.book_order;
    const SECTION_ORDER = ['目标意图','课文解说','单元学习任务','单元研习任务','教学设计','资料链接','其他','编写说明'];
    let curBook = BOOK_ORDER[0];
    let cur = null;

    function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function openSide(){ document.getElementById('side').classList.add('open'); document.getElementById('mask').style.display='block'; }
    function closeSide(){ document.getElementById('side').classList.remove('open'); document.getElementById('mask').style.display='none'; }
    function renderCrumbs(p){ return p.split('/').filter(Boolean).map(x=>esc(x)).join(' › '); }
    function isHeading(p){
      if(p.length > 40) return false;
      if(/^《.*》译文/.test(p)) return true;
      if(/^[一二三四五六七八九十]+[、.．]/.test(p)) return true;
      if(/^\\d+[.、．]/.test(p)) return true;
      if(/^（[一二三四五六七八九十]+）/.test(p)) return true;
      if(/^\([一二三四五六七八九十]+\)/.test(p)) return true;
      return false;
    }
    function extractHeadings(c){
      const heads = [];
      let hidx = 0;
      c.split('\\n').forEach(p=>{
        p = p.trim();
        if(!p) return;
        if(isHeading(p)) heads.push({text:p, id:'h'+(hidx++)});
      });
      return heads;
    }
    function renderContent(c, heads){
      let hidx = 0;
      const parts = c.split('\\n');
      return parts.map(p=>{
        p = p.trim();
        if(!p) return '';
        if(p === '---') return '<hr>';
        if(isHeading(p)){
          const id = 'h' + (hidx++);
          return '<div class="h" id="'+id+'">'+esc(p)+'</div>';
        }
        return '<p>'+esc(p)+'</p>';
      }).join('');
    }
    function showDoc(book, unit, section, doc, ev){
      cur = {book, unit, section, title: doc.t};
      document.getElementById('crumbs').innerHTML = renderCrumbs(doc.p);
      document.getElementById('title').textContent = doc.t;
      const heads = extractHeadings(doc.c);
      let tocHtml = '';
      if(heads.length >= 2){
        tocHtml = '<div id="toc-inner"><div class="toc-title">📑 本节目录（' + heads.length + ' 节）</div>' +
          heads.map(h=>'<a class="toc-item" href="#'+h.id+'">'+esc(h.text)+'</a>').join('') + '</div>';
      }
      document.getElementById('content').innerHTML = tocHtml + renderContent(doc.c, heads);
      // 本节目录点击 → 平滑滚动 + 高亮
      document.querySelectorAll('#content .toc-item').forEach(a=>{
        a.onclick = function(e){
          e.preventDefault();
          const el = document.getElementById(this.getAttribute('href').slice(1));
          if(el){ el.scrollIntoView({behavior:'smooth', block:'start'}); el.classList.remove('h-highlight'); void el.offsetWidth; el.classList.add('h-highlight'); }
        };
      });
      document.getElementById('hint').style.display = 'none';
      document.getElementById('cur-book').textContent = book;
      document.querySelectorAll('#tree .node').forEach(n=>n.classList.remove('sel'));
      if(ev && ev.currentTarget) ev.currentTarget.classList.add('sel');
      if(window.innerWidth <= 720) closeSide();
    }
    function renderTree(){
      const b = curBook;
      const box = document.getElementById('tree');
      box.innerHTML = '';
      document.querySelectorAll('.btab').forEach(t=>t.classList.toggle('active', t.dataset.book===b));
      const book = DATA.books[b] || {};
      let firstDoc = null;
      for(const unit of Object.keys(book)){
        const uEl = document.createElement('div');
        uEl.className = 'node unit';
        uEl.textContent = unit;
        box.appendChild(uEl);
        const sections = book[unit];
        const sKeys = Object.keys(sections).sort((a,c)=>{
          const ia = SECTION_ORDER.findIndex(o=>a===o), ic = SECTION_ORDER.findIndex(o=>c===o);
          return (ia<0?99:ia) - (ic<0?99:ic);
        });
        for(const sec of sKeys){
          const sEl = document.createElement('div');
          sEl.className = 'node section';
          sEl.textContent = sec;
          box.appendChild(sEl);
          const docs = sections[sec];
          if(!docs.length){ const e=document.createElement('div'); e.className='node empty'; e.textContent='（无）'; box.appendChild(e); continue; }
          for(const d of docs){
            const dEl = document.createElement('div');
            dEl.className = 'node doc' + (sec==='课文解说'?' ke':'');
            dEl.textContent = d.t;
            dEl.onclick = (ev)=>showDoc(b, unit, sec, d, ev);
            box.appendChild(dEl);
            if(!firstDoc) firstDoc = {unit, sec, d};
          }
        }
      }
      if(firstDoc && !cur) showDoc(b, firstDoc.unit, firstDoc.sec, firstDoc.d);
    }
    function doSearch(){
      const q = document.getElementById('search').value.trim().toLowerCase();
      const box = document.getElementById('tree');
      const cnt = document.getElementById('result-count');
      if(!q){ cnt.textContent=''; renderTree(); return; }
      box.innerHTML = '';
      let n = 0;
      for(const b of BOOK_ORDER){
        const book = DATA.books[b] || {};
        for(const unit of Object.keys(book)){
          for(const sec of Object.keys(book[unit])){
            for(const d of book[unit][sec]){
              const hay = (d.t + '\\n' + d.c).toLowerCase();
              if(hay.includes(q)){
                n++;
                const el = document.createElement('div');
                el.className = 'node doc';
                el.textContent = `[${b}] ${unit} › ${d.t}`;
                el.onclick = (ev)=>showDoc(b, unit, sec, d, ev);
                box.appendChild(el);
              }
            }
          }
        }
      }
      cnt.textContent = n ? `命中 ${n} 条` : '无结果';
      if(!n){ const e=document.createElement('div'); e.className='node empty'; e.textContent='（无匹配）'; box.appendChild(e); }
    }
    // 册目标签
    const tabs = document.getElementById('book-tabs');
    for(const b of BOOK_ORDER){
      const t = document.createElement('div');
      t.className = 'btab';
      t.dataset.book = b;
      t.textContent = b.replace('选择性必修','选必').replace('必修','必修');
      t.onclick = ()=>{ curBook = b; cur = null; renderTree(); };
      tabs.appendChild(t);
    }
    document.getElementById('menu-btn').onclick = openSide;
    document.getElementById('close-btn').onclick = closeSide;
    document.getElementById('mask').onclick = closeSide;
    document.getElementById('search').addEventListener('input', doSearch);
    document.getElementById('search').addEventListener('keydown', e=>{ if(e.key==='Enter') doSearch(); });
    renderTree();
    '''

    html_out = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>高中语文教参库 · 查询器</title>
<style>{css}</style>
</head>
<body>
<div id="topbar">
  <button id="menu-btn">☰ 目录</button>
  <h1>📖 高中语文教参库</h1>
  <span id="cur-book">{BOOK_ORDER[0]}</span>
</div>
<div id="mask"></div>
<div id="side">
  <div id="side-head">
    <div class="row"><h2>📚 目录</h2><button id="close-btn">✕</button></div>
    <input id="search" type="text" placeholder="🔍 搜索：课文 / 译文 / 实词 / 文学短评…">
    <div id="book-tabs"></div>
  </div>
  <div id="tree"></div>
  <div id="result-count"></div>
  <div class="footer">统编版《教师教学用书》（人教社）· 仅供学习 · 非商用</div>
</div>
<div id="main">
  <div id="crumbs"></div>
  <h1 id="title"></h1>
  <div id="content"></div>
  <div id="hint"><b>使用说明</b><br><br>
    1. 点左上角「☰ 目录」打开菜单，选册 → 展开单元 → 点「课文解说」看解读<br>
    2. 目录里搜索框输入关键词（如「劝学」「意象」「文学短评」），即全文搜索<br>
    3. 文言文标准译文在「资料链接」→「文言文参考译文」<br><br>
    <span style="font-size:13px;color:#9ca3af">五册 282 节点 · 116 篇课文解说 · 约 161 万字</span>
  </div>
</div>
<script>
{js.replace('__DATA__', data_json)}
</script>
</body>
</html>'''

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html_out)
    print(f'OK: {OUT} ({os.path.getsize(OUT)/1024/1024:.1f}MB)')

if __name__ == '__main__':
    main()
