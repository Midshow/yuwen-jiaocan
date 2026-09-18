# -*- coding: utf-8 -*-
"""FlowUs 教参 tree JSON -> SQLite 结构化数据库（册→单元→课文→解读/任务/设计/资料）
每个 doc 节点一条记录：uuid/parent_id/type/title/content(递归合并正文)/depth/ord/路径
"""
import json, os, re, sqlite3, sys

OUT = os.environ.get('FLOWUS_DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flowus_data'))
DB = os.path.join(OUT, '高中语文教参.db')

BOOKS = {
    '必修上册': '96fe42db-fdc8-4f5b-85be-9bc252193ee9',
    '必修下册': '6c483240-6ffd-4921-9354-29907c6c2e88',
    '选择性必修上册': 'e84932fb-69da-496a-b32f-0f862280e66f',
    '选择性必修中册': '50b613c3-1549-47b1-8619-4042b50d7117',
    '选择性必修下册': '91acf2ef-ce8e-4edd-98a9-8df4fdd769d3',
}

def clean_text(t):
    t = str(t).replace('\u200b', '').replace('\ufeff', '').replace('\xa0', ' ')
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()

def seg_text(segs):
    return clean_text(''.join(str(s.get('text', '')) for s in (segs or [])))

def build_book(book_name, root_id, conn):
    tree_fp = os.path.join(OUT, f'{book_name}_tree.json')
    with open(tree_fp, encoding='utf-8') as f:
        tree = json.load(f)
    # 所有 doc 的索引
    all_docs = {}
    for parent_id, children in tree.items():
        for k, d in children.items():
            all_docs[k] = d

    rows = []          # 最终入库行
    path_stack = []    # 标题路径（用于定位）
    visited = set()

    def doc_title(d):
        t = seg_text((d.get('data') or {}).get('segments') or []) or ''
        if not t:
            t = d.get('title') or ''
        return clean_text(t)

    def collect_content(did, seen):
        """递归收集一个 doc 的正文文本（子块 type 1/6/13 等），返回 (text, sub_doc_ids)
        sub_doc_ids: 遇到的独立子页（type=0 且在 tree 中）"""
        d = all_docs.get(did)
        if not d or did in seen:
            return '', []
        seen.add(did)
        parts = []
        sub_docs = []
        sub_ids = d.get('subNodes') or []
        if not sub_ids:
            sub_ids = [bid for bid in (tree.get(did) or {}) if bid != did]
        for sid in sub_ids:
            b = all_docs.get(sid)
            if not b:
                continue
            bt = b.get('type')
            btxt = seg_text((b.get('data') or {}).get('segments') or [])
            if bt == 0 and sid in tree:
                sub_docs.append(sid)  # 独立子页
            elif bt in (0, 38, 27):
                # 内部容器：标题 + 递归子块
                if btxt:
                    parts.append(btxt)
                inner_txt, inner_sub = collect_content(sid, seen)
                if inner_txt:
                    parts.append(inner_txt)
                sub_docs.extend(inner_sub)
            elif bt in (1, 6, 13):
                if btxt:
                    parts.append(btxt)
            elif bt == 9:
                parts.append('---')
        return '\n'.join(parts), sub_docs

    def walk(did, depth, ord_in_parent):
        if did in visited or did not in all_docs:
            return
        visited.add(did)
        d = all_docs[did]
        title = doc_title(d)
        path_stack.append(title)
        # 递归收集正文 + 子页列表（注意：collect_content 内部处理容器，子页仅记录不深展内容）
        content, sub_docs = collect_content(did, set())
        rows.append({
            'uuid': did,
            'book': book_name,
            'parent_id': d.get('parentId'),
            'type': d.get('type'),
            'title': title,
            'content': content,
            'depth': depth,
            'ord': ord_in_parent,
            'path': '/'.join(path_stack),
        })
        sub_ids = d.get('subNodes') or []
        if not sub_ids:
            sub_ids = [bid for bid in (tree.get(did) or {}) if bid != did]
        # 只对"独立子页"递归；容器块已在 collect_content 中处理
        child_ord = 0
        for sid in sub_ids:
            b = all_docs.get(sid)
            if b and b.get('type') == 0 and sid in tree and sid not in visited:
                walk(sid, depth + 1, child_ord)
                child_ord += 1
        path_stack.pop()

    walk(root_id, 1, 0)
    # 落库
    cur = conn.cursor()
    cur.execute("DELETE FROM docs WHERE book=?", (book_name,))
    cur.executemany(
        "INSERT OR REPLACE INTO docs (uuid, book, parent_id, type, title, content, depth, ord, path) "
        "VALUES (:uuid,:book,:parent_id,:type,:title,:content,:depth,:ord,:path)", rows)
    conn.commit()
    return len(rows)

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS docs (
        uuid TEXT PRIMARY KEY,
        book TEXT NOT NULL,
        parent_id TEXT,
        type INTEGER,
        title TEXT,
        content TEXT,
        depth INTEGER,
        ord INTEGER,
        path TEXT
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_book ON docs(book)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parent ON docs(parent_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_type ON docs(type)")
    conn.commit()
    total = 0
    for book, root_id in BOOKS.items():
        n = build_book(book, root_id, conn)
        print(f'OK {book}: {n} docs')
        total += n
    print(f'TOTAL: {total} docs -> {DB}')
    conn.close()

if __name__ == '__main__':
    main()
