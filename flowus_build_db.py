# -*- coding: utf-8 -*-
"""FlowUs 教参 tree JSON -> SQLite 结构化数据库（册→单元→课文→解读/任务/设计/资料）
每个 doc 节点一条记录：uuid/parent_id/type/title/content(递归合并正文)/depth/ord/路径
"""
import argparse, json, os, re, sqlite3, sys, tempfile
from pathlib import Path
from jiaocan.core import database_path

OUT = os.environ.get('FLOWUS_DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flowus_data'))

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

def build_book(book_name, root_id, conn, data_dir=None, report=None):
    tree_fp = os.path.join(data_dir or OUT, f'{book_name}_tree.json')
    with open(tree_fp, encoding='utf-8') as f:
        tree = json.load(f)
    # 所有 doc 的索引
    all_docs = {}
    report = report if report is not None else {}
    report.update(conflicting_ids=[], missing_blocks=[], unknown_types=[], unreachable_pages=[])
    for parent_id, children in tree.items():
        for k, d in children.items():
            if k in all_docs and all_docs[k] != d:
                report['conflicting_ids'].append(k)
            all_docs[k] = d
    if root_id not in all_docs:
        raise ValueError(f'{book_name}: 根节点 {root_id} 缺失，已停止构建。')
    if report['conflicting_ids']:
        raise ValueError(f"{book_name}: 存在冲突的重复节点：{report['conflicting_ids']}")

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
                report['missing_blocks'].append(sid)
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
                inner_txt, inner_sub = collect_content(sid, seen)
                if inner_txt:
                    parts.append(inner_txt)
                sub_docs.extend(inner_sub)
            elif bt == 9:
                parts.append('---')
            else:
                report['unknown_types'].append({'id': sid, 'type': bt})
                if btxt:
                    parts.append(btxt)
                inner_txt, inner_sub = collect_content(sid, seen)
                if inner_txt:
                    parts.append(inner_txt)
                sub_docs.extend(inner_sub)
        return '\n'.join(parts), sub_docs

    def walk(did, depth, ord_in_parent, page_parent=None):
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
            'parent_id': page_parent,
            'type': d.get('type'),
            'title': title,
            'content': content,
            'depth': depth,
            'ord': ord_in_parent,
            'path': '/'.join(path_stack),
        })
        # collect_content 已按原顺序发现容器内的独立子页。
        child_ord = 0
        for sid in sub_docs:
            if sid not in visited:
                walk(sid, depth + 1, child_ord, did)
                child_ord += 1
        path_stack.pop()

    walk(root_id, 1, 0)
    report['unreachable_pages'] = sorted(k for k,d in all_docs.items() if d.get('type') == 0 and k in tree and k not in visited)
    report['nodes'] = len(rows)
    report['empty_content'] = [r['uuid'] for r in rows if not r['content']]
    paths = [r['path'] for r in rows]
    report['duplicate_paths'] = sorted({p for p in paths if paths.count(p) > 1})
    if report['missing_blocks'] or report['unreachable_pages']:
        raise ValueError(f'{book_name}: 存在缺失块或未遍历子页，已停止构建；请检查原始 tree JSON。')
    # 落库
    cur = conn.cursor()
    cur.execute("DELETE FROM docs WHERE book=?", (book_name,))
    cur.executemany(
        "INSERT INTO docs (uuid, book, parent_id, type, title, content, depth, ord, path) "
        "VALUES (:uuid,:book,:parent_id,:type,:title,:content,:depth,:ord,:path)", rows)
    return len(rows)

def create_schema(conn):
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

def validate_database(conn):
    return {
        'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0],
        'books': [dict(book=b, nodes=n, empty_content=e) for b,n,e in conn.execute("SELECT book,COUNT(*),SUM(CASE WHEN content='' OR content IS NULL THEN 1 ELSE 0 END) FROM docs GROUP BY book")],
        'orphan_nodes': [r[0] for r in conn.execute('SELECT d.uuid FROM docs d LEFT JOIN docs p ON d.parent_id=p.uuid WHERE d.depth>1 AND p.uuid IS NULL')],
        'duplicate_paths': [list(r) for r in conn.execute('SELECT book,path,COUNT(*) FROM docs GROUP BY book,path HAVING COUNT(*)>1')],
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description='从五册 tree JSON 原子构建教参库，或校验现有数据库')
    parser.add_argument('--db'); parser.add_argument('--data-dir', default=OUT)
    parser.add_argument('--report', help='JSON 校验报告输出路径')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    target = database_path(args.db); report = {}; temp = None
    if args.report and Path(args.report).resolve() == target:
        parser.error('--report 不能与数据库路径相同')
    try:
        if args.check:
            from jiaocan.core import connect
            conn = connect(target)
            try: report = validate_database(conn)
            finally: conn.close()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(dir=target.parent, suffix='.tmp'); os.close(fd)
            conn = sqlite3.connect(temp)
            try:
                create_schema(conn)
                report['sources'] = {}
                with conn:
                    for book, root_id in BOOKS.items():
                        report['sources'][book] = {}
                        build_book(book, root_id, conn, args.data_dir, report['sources'][book])
                report.update(validate_database(conn))
            finally: conn.close()
            if report['integrity'] != 'ok' or report['orphan_nodes'] or report['duplicate_paths']:
                raise ValueError('构建校验未通过，原数据库保持不变。')
            os.replace(temp, target); temp = None
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get('integrity') == 'ok' and not report.get('orphan_nodes') and not report.get('duplicate_paths') else 2
    except (OSError, ValueError, sqlite3.Error) as exc:
        report['error'] = str(exc); print(f'错误：{exc}', file=sys.stderr); return 2
    finally:
        if temp: Path(temp).unlink(missing_ok=True)
        if args.report:
            out = Path(args.report); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    raise SystemExit(main())
