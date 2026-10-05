import os
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ['必修上册', '必修下册', '选择性必修上册', '选择性必修中册', '选择性必修下册']


def database_path(value=None):
    if value:
        return Path(value).expanduser().resolve()
    if os.environ.get('FLOWUS_DB'):
        return Path(os.environ['FLOWUS_DB']).expanduser().resolve()
    return Path(os.environ.get('FLOWUS_DATA_DIR', ROOT / 'flowus_data')).expanduser().resolve() / '高中语文教参.db'


def connect(value=None):
    path = database_path(value)
    if not path.is_file():
        raise ValueError(f'数据库不存在：{path}。请复制完整 flowus_data 目录，或使用 --db 指定数据库。')
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('SELECT uuid, book, parent_id, title, content, depth, ord, path FROM docs LIMIT 1')
    except sqlite3.Error:
        conn.close()
        raise ValueError(f'数据库格式无效：{path}；需要含 docs 表的教参库。') from None
    return conn


def normalize(title):
    title = re.sub(r'^\s*\d+(?:[.．]\d+)*[.．、]?\s*', '', title)
    return re.sub(r'[\s《》〈〉“”"\'（）()·：:，,。]', '', title).casefold()


def heading(line):
    return len(line) <= 80 and bool(re.match(r'^(?:[一二三四五六七八九十]+[、.．]|\d+[.、．]|[（(][一二三四五六七八九十]+[）)]|《.*》.*译文)', line))


def ordered_docs(conn):
    rows = [dict(r) for r in conn.execute('SELECT * FROM docs')]
    by_id = {r['uuid']: r for r in rows}
    by_path = {(r['book'], r['path']): r for r in rows}
    def key(row, seen=None):
        seen = set() if seen is None else seen
        if row['uuid'] in seen: return ()
        seen.add(row['uuid'])
        parent = by_id.get(row['parent_id']) or by_path.get((row['book'], row['path'].rsplit('/', 1)[0]))
        prefix = key(parent, seen) if parent and parent is not row else ()
        return prefix + ((row['ord'] or 0, row['title'] or ''),)
    rows.sort(key=lambda r: (BOOKS.index(r['book']) if r['book'] in BOOKS else len(BOOKS), key(r), r['uuid']))
    for row in rows:
        parts = row['path'].split('/')
        row.update(doc_id=row['uuid'], unit=parts[1] if len(parts) > 1 else '',
                   section=parts[2] if len(parts) > 2 else '', subsection='', content=row['content'] or '')
    return rows


def snippet(content, words, radius=65):
    positions = [content.casefold().find(w.casefold()) for w in words]
    pos = min((p for p in positions if p >= 0), default=0)
    start = max(0, pos - radius)
    end = min(len(content), pos + radius + max(map(len, words), default=0))
    return ('…' if start else '') + content[start:end].replace('\n', ' ') + ('…' if end < len(content) else '')


def search(docs, query, book=None):
    words = query.casefold().split()
    if not words: return []
    rows = [r for r in docs if (not book or r['book'] == book)
            and all(w in (r['title'] + '\n' + r['content']).casefold() for w in words)]
    q = normalize(query)
    def rank(r):
        title = normalize(r['title'])
        return 0 if title == q else (1 if q in title else 2)
    return [dict(r, snippet=snippet(r['content'], words), rank=rank(r)) for r in sorted(rows, key=rank)]


def translations(docs):
    """Extract only explicitly marked translations; retain exact source line ranges."""
    results = []
    for row in docs:
        lines = row['content'].splitlines()
        groups = []
        for i, line in enumerate(lines):
            if re.match(r'^[一二三四五六七八九十]+[、.．].*译文\s*[:：]?$', line):
                end = next((j for j in range(i+1, len(lines)) if re.match(r'^[一二三四五六七八九十]+[、.．]', lines[j])), len(lines))
                named = re.search(r'《(.+)》.*译文', line)
                if named:
                    groups.append((named.group(1), i, end, line))
                else:
                    starts = [(j, re.match(r'^\d+[.．、]\s*《(.+)》\s*$', lines[j])) for j in range(i+1, end)]
                    starts = [(j,m) for j,m in starts if m]
                    for n,(j,m) in enumerate(starts):
                        stop = starts[n+1][0] if n+1 < len(starts) else end
                        groups.append((m.group(1), j, stop, line + ' / ' + lines[j]))
            elif re.match(r'^《.+》(?:参考)?译文\s*[:：]?$', line):
                end = next((j for j in range(i+1, len(lines)) if heading(lines[j])), len(lines))
                groups.append((re.match(r'^《(.+)》', line).group(1), i, end, line))
        for title, start, end, label in groups:
            body = '\n'.join(lines[start+1:end]).strip()
            if body:
                results.append(dict(row, title=title, content=body, subsection=label,
                                    start_line=start+1, end_line=end, translation_id=f"{row['doc_id']}:{start+1}"))
    return results


def related(docs, row, translation_rows=None):
    same = [d for d in docs if d['book'] == row['book'] and d['unit'] == row['unit']]
    trs = translations(same) if translation_rows is None else translation_rows
    return {
        'translations': [t for t in trs if t['book'] == row['book'] and t['unit'] == row['unit'] and normalize(t['title']) == normalize(row['title'])],
        'tasks': [d for d in same if ('学习任务' in d['title'] or '研习任务' in d['title']) and d['content']],
        'materials': [d for d in same if '资料链接' in d['title'] and d['content']],
    }
