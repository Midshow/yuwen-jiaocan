# -*- coding: utf-8 -*-
"""高中语文教参查询引擎（问答交互核心）
用法：
  python flowus_query.py search <关键词>            # 全文搜索，返回命中节点+摘要
  python flowus_query.py book <册名>                # 册目录（单元级）
  python flowus_query.py unit <册名> <单元关键词>    # 单元栏目列表
  python flowus_query.py get <册名> <标题关键词>     # 取节点全文
  python flowus_query.py text <册名> <课文关键词>    # 课文解说（智能定位 课文解说/xx）
  python flowus_query.py list-ke <关键词>           # 列出相关课文解说
"""
import sqlite3, sys, os, re

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flowus_data', '高中语文教参.db')

def connect():
    return sqlite3.connect(DB)

def show(r, brief=False):
    book, path, title, content, depth = r
    if brief:
        print(f'[{book}] {path}  ({len(content)}字)')
    else:
        print(f'═══ [{book}] {path} ═══')
        print(content)
        print()

def cmd_search(keywords, limit=8):
    conn = connect(); cur = conn.cursor()
    for kw in keywords:
        cur.execute("SELECT book, path, title, content, depth FROM docs WHERE content LIKE ? OR title LIKE ? ORDER BY LENGTH(content) DESC LIMIT ?",
                    (f'%{kw}%', f'%{kw}%', limit))
        rows = cur.fetchall()
        print(f'—— 命中「{kw}」{len(rows)} 条 ——')
        for r in rows:
            show(r, brief=True)
        print()

def cmd_book(book, conn=None):
    conn = conn or connect(); cur = conn.cursor()
    cur.execute("SELECT title, path, LENGTH(content) FROM docs WHERE book=? AND depth=2 ORDER BY ord", (book,))
    for t, p, n in cur.fetchall():
        print(f'  {t}  ({n}字)')

def cmd_unit(book, unit_kw, conn=None):
    conn = conn or connect(); cur = conn.cursor()
    cur.execute("SELECT path, title, LENGTH(content) FROM docs WHERE book=? AND title LIKE ? AND depth>=3 ORDER BY path", (book, f'%{unit_kw}%'))
    rows = cur.fetchall()
    if not rows:
        # 按路径找单元
        cur.execute("SELECT path, title, LENGTH(content) FROM docs WHERE book=? AND path LIKE ? AND depth>=3 ORDER BY path", (book, f'%{unit_kw}%'))
        rows = cur.fetchall()
    for p, t, n in rows:
        label = '（目录节点）' if n == 0 else f'[{n}字]'
        print(f'  {label} {p}')

def cmd_get(book, title_kw, conn=None, limit=3):
    conn = conn or connect(); cur = conn.cursor()
    cur.execute("SELECT book, path, title, content, depth FROM docs WHERE book=? AND (title LIKE ? OR path LIKE ?) ORDER BY depth DESC LIMIT ?",
                (book, f'%{title_kw}%', f'%{title_kw}%', limit))
    rows = cur.fetchall()
    if not rows:
        cur.execute("SELECT book, path, title, content, depth FROM docs WHERE title LIKE ? ORDER BY depth DESC LIMIT ?", (f'%{title_kw}%', limit))
        rows = cur.fetchall()
    for r in rows:
        show(r)

def cmd_text(book, ke_kw, conn=None):
    """智能定位课文解说：优先 path 含 课文解说/关键词"""
    conn = conn or connect(); cur = conn.cursor()
    cur.execute("SELECT book, path, title, content, depth FROM docs WHERE book=? AND path LIKE '%课文解说%' AND title LIKE ? ORDER BY LENGTH(content) DESC",
                (book, f'%{ke_kw}%'))
    rows = cur.fetchall()
    if not rows:
        cur.execute("SELECT book, path, title, content, depth FROM docs WHERE book=? AND path LIKE '%课文解说%' AND path LIKE ? ORDER BY LENGTH(content) DESC",
                    (book, f'%{ke_kw}%'))
        rows = cur.fetchall()
    for r in rows:
        show(r)

def cmd_list_ke(kw=None, conn=None):
    conn = conn or connect(); cur = conn.cursor()
    if kw:
        cur.execute("SELECT book, path, title, content, depth FROM docs WHERE path LIKE '%课文解说/%' AND (title LIKE ? OR book LIKE ? OR path LIKE ?) ORDER BY book, path", (f'%{kw}%', f'%{kw}%', f'%{kw}%'))
    else:
        cur.execute("SELECT book, path, title, content, depth FROM docs WHERE path LIKE '%课文解说/%' ORDER BY book, path")
    rows = cur.fetchall()
    print(f'课文解说共 {len(rows)} 篇')
    for r in rows:
        print(f'  {r[0]}|{r[2]}|{len(r[3])}字')

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    cmd = args[0]
    try:
        if cmd == 'search':
            cmd_search(args[1:])
        elif cmd == 'book':
            cmd_book(args[1])
        elif cmd == 'unit':
            cmd_unit(args[1], args[2])
        elif cmd == 'get':
            cmd_get(args[1], args[2])
        elif cmd == 'text':
            cmd_text(args[1], args[2])
        elif cmd == 'list-ke':
            cmd_list_ke(args[1] if len(args) > 1 else None)
        else:
            print(__doc__)
    except IndexError:
        print(__doc__)

if __name__ == '__main__':
    main()
