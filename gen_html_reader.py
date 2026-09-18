# -*- coding: utf-8 -*-
"""SQLite 教参库 → 单文件 HTML 查询器（同学可用版）
数据内嵌 JSON（282 节点/约 161 万字），浏览器双击即开，零依赖零命令。
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

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # 取所有节点（深度>=2，含路径）
    cur.execute("SELECT book, path, title, content, depth, ord FROM docs ORDER BY book, path, ord")
    rows = cur.fetchall()

    # 组树：book -> {unit -> {section -> [docs]}}
    books = {}
    ke_index = []  # 课文解说快捷索引
    for book, path, title, content, depth, ord_ in rows:
        if depth < 2:
            continue
        parts = [p for p in path.split('/') if p]
        if len(parts) < 2:
            continue
        unit = parts[1] if len(parts) > 1 else '其他'
        # 段落内栏目判断：用标题或路径中含栏目关键词
        section = None
        for kw, label in SECTION_KEYWORDS.items():
            if kw in path or kw in title:
                section = label
                break
        if section is None:
            # 路径中最后一段是课文名且父是课文解说 → 归课文解说
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

    # 课文解说按册聚合索引
    ke_by_book = {}
    for item in sorted(ke_index, key=lambda x: (BOOK_ORDER.index(x['book']) if x['book'] in BOOK_ORDER else 9, x['title'])):
        ke_by_book.setdefault(item['book'], []).append(item)

    data = {'books': books, 'ke': ke_by_book, 'book_order': BOOK_ORDER}
    data_json = json.dumps(data, ensure_ascii=False)

    print(f'节点数: {len(rows)} | JSON 体积: {len(data_json.encode("utf-8"))/1024:.0f}KB')

    # ============ HTML 模板 ============
    css = '''
    :root { --c-main:#1f2937; --c-accent:#2563eb; --c-bg:#f8fafc; --c-side:#111827; --c-side-txt:#d1d5db; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif; color:var(--c-main); background:var(--c-bg); height:100vh; overflow:hidden; }
    #app { display:flex; height:100vh; }
    #side { width:330px; min-width:330px; background:var(--c-side); color:var(--c-side-txt); display:flex; flex-direction:column; }
    #side-head { padding:14px 16px; border-bottom:1px solid #1f2937; }
    #side-head h1 { font-size:17px; color:#fff; margin:0 0 10px; }
    #search { width:100%; padding:8px 10px; border-radius:6px; border:1px solid #374151; background:#1f2937; color:#fff; font-size:14px; }
    #search::placeholder { color:#6b7280; }
    #book-tabs { display:flex; gap:4px; padding:10px 12px 4px; flex-wrap:wrap; }
    .btab { padding:4px 10px; border-radius:14px; font-size:12px; background:#1f2937; color:#9ca3af; cursor:pointer; border:1px solid #374151; }
    .btab.active { background:#2563eb; color:#fff; border-color:#2563eb; }
    #tree { flex:1; overflow-y:auto; padding:8px 6px 20px; font-size:13px; }
    .node { padding:4px 8px; border-radius:4px; cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .node:hover { background:#1f2937; }
    .node.sel { background:#2563eb; color:#fff; }
    .node.unit { color:#fff; font-weight:bold; margin-top:6px; }
    .node.section { color:#93c5fd; font-size:12px; }
    .node.doc { color:#9ca3af; padding-left:20px; }
    .node.ke { color:#d1d5db; }
    .node.empty { color:#4b5563; font-style:italic; cursor:default; }
    #main { flex:1; overflow-y:auto; padding:20px 28px 80px; }
    #crumbs { font-size:12px; color:#6b7280; margin-bottom:8px; }
    #title { font-size:24px; color:#1d4ed8; border-bottom:2px solid #2563eb; padding-bottom:8px; margin:0 0 16px; }
    #content { line-height:1.9; font-size:15px; }
    #content p { margin:8px 0; text-align:justify; }
    #content .h { font-weight:bold; color:#b45309; margin:18px 0 6px; }
    #content hr { border:none; border-top:1px dashed #cbd5e1; margin:14px 0; }
    #content blockquote { background:#fef3c7; border-left:4px solid #f59e0b; margin:10px 0; padding:8px 12px; border-radius:4px; }
    #hint { color:#6b7280; text-align:center; margin-top:80px; font-size:15px; }
    #hint b { color:#2563eb; }
    #result-count { padding:6px 12px; font-size:12px; color:#f59e0b; }
    .footer { padding:10px 16px; font-size:11px; color:#4b5563; border-top:1px solid #e5e7eb; background:#fff; }
    @media (max-width:720px) {
      #side { width:100%; min-width:0; height:45vh; }
      #app { flex-direction:column; }
      #main { padding:14px; }
      #title { font-size:20px; }
    }
    '''

    js = '''
    const DATA = __DATA__;
    const BOOK_ORDER = DATA.book_order;
    let cur = null; // {book, unit, section, title}

    function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function renderCrumbs(p){ return p.split('/').filter(Boolean).map(x=>esc(x)).join(' › '); }
    function renderContent(c){
      const parts = c.split('\\n');
      return parts.map(p=>{
        p = p.trim();
        if(!p) return '';
        if(p === '---') return '<hr>';
        if(/^《.*》译文/.test(p)) return '<div class="h">'+esc(p)+'</div>';
        if(/^[一二三四五六七八九十]+[、.．]/.test(p) && p.length < 40) return '<div class="h">'+esc(p)+'</div>';
        return '<p>'+esc(p)+'</p>';
      }).join('');
    }
    function showDoc(book, unit, section, doc, ev){
      cur = {book, unit, section, title: doc.t};
      document.getElementById('crumbs').innerHTML = renderCrumbs(doc.p);
      document.getElementById('title').textContent = doc.t;
      document.getElementById('content').innerHTML = renderContent(doc.c);
      document.getElementById('hint').style.display = 'none';
      // 高亮树节点
      document.querySelectorAll('.node').forEach(n=>n.classList.remove('sel'));
      if(ev && ev.currentTarget) ev.currentTarget.classList.add('sel');
    }
    function renderTree(){
      const b = cur ? cur.book : BOOK_ORDER[0];
      const box = document.getElementById('tree');
      box.innerHTML = '';
      document.querySelectorAll('.btab').forEach(t=>t.classList.toggle('active', t.dataset.book===b));
      const book = DATA.books[b] || {};
      let firstDoc = null;
      const unitNames = Object.keys(book).sort((a,c)=> a.localeCompare(c, 'zh'));
      for(const unit of unitNames){
        const uEl = document.createElement('div');
        uEl.className = 'node unit';
        uEl.textContent = unit;
        box.appendChild(uEl);
        const sections = book[unit];
        // 栏目顺序：目标意图/课文解说/学习任务/教学设计/资料链接/其他/编写说明
        const order = ['目标意图','课文解说','单元学习任务','单元研习任务','教学设计','资料链接','其他','编写说明'];
        const sKeys = Object.keys(sections).sort((a,c)=>{
          const ia = order.findIndex(o=>a.includes(o)), ic = order.findIndex(o=>c.includes(o));
          return (ia<0?99:ia) - (ic<0?99:ic) || a.localeCompare(c,'zh');
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
    function initKeQuick(){
      // 课文解说快捷入口（每册下拉）
      const tabs = document.getElementById('book-tabs');
      for(const b of BOOK_ORDER){
        const t = document.createElement('div');
        t.className = 'btab' + (b===BOOK_ORDER[0]?' active':'');
        t.dataset.book = b;
        t.textContent = b.replace('选择性必修','选必').replace('必修','必修');
        t.onclick = ()=>{ cur = null; renderTree(); };
        tabs.appendChild(t);
      }
    }
    initKeQuick();
    renderTree();
    document.getElementById('search').addEventListener('input', doSearch);
    document.getElementById('search').addEventListener('keydown', e=>{ if(e.key==='Enter') doSearch(); });
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
<div id="app">
  <div id="side">
    <div id="side-head">
      <h1>📖 高中语文教参库</h1>
      <input id="search" type="text" placeholder="🔍 搜索：课文 / 译文 / 实词 / 文学短评…（回车或输入即搜）">
      <div id="book-tabs"></div>
    </div>
    <div id="tree"></div>
    <div id="result-count"></div>
    <div class="footer">数据：统编版高中语文《教师教学用书》（人教社）· 仅供学习使用 · 非商用</div>
  </div>
  <div id="main">
    <div id="crumbs"></div>
    <h1 id="title"></h1>
    <div id="content"></div>
    <div id="hint"><b>使用说明</b><br><br>
      1. 左侧选册 → 展开单元 → 点「课文解说」看解读（文言文译文在「资料链接」→ 文言文参考译文）<br>
      2. 顶部搜索框输入关键词（如「劝学」「意象」「文学短评」），回车即全文搜索<br>
      3. 手机亦可：顶部选册，左右滑动浏览<br><br>
      <span style="font-size:13px;color:#9ca3af">五册 282 节点 · 116 篇课文解说 · 约 161 万字</span>
    </div>
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
