"""Build the portable offline reader from the shared query engine."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from jiaocan.core import ROOT, BOOKS, connect, database_path, ordered_docs, translations, related


def build(db=None, output=None):
    conn = connect(db)
    try:
        docs = ordered_docs(conn)
    finally:
        conn.close()
    trs = translations(docs)
    for row in docs:
        links = related(docs, row, trs) if '/课文解说/' in row['path'] else {}
        row['links'] = {k: [x.get('translation_id', x['doc_id']) for x in v] for k,v in links.items()}
        row['id'] = row['doc_id']
    for row in trs:
        row['id'] = row['translation_id']
        row['links'] = {'source': [row['doc_id']]}
    data = json.dumps({'books': BOOKS, 'docs': docs, 'translations': trs}, ensure_ascii=False).replace('<', '\\u003c')
    assets = ROOT / 'reader'
    html = (assets / 'index.html').read_text(encoding='utf-8')
    html = html.replace('__CSS__', (assets / 'style.css').read_text(encoding='utf-8'))
    html = html.replace('__JS__', (assets / 'app.js').read_text(encoding='utf-8'))
    html = html.replace('__DATA__', data)
    out = Path(output) if output else ROOT / 'yuwen-jiaocan.html'
    if out.resolve() == database_path(db):
        raise ValueError('HTML 输出路径不能覆盖数据库')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='生成可离线使用的单文件教参阅读器')
    parser.add_argument('--db')
    parser.add_argument('--output', default=str(ROOT / 'yuwen-jiaocan.html'))
    args = parser.parse_args(argv)
    try:
        out = build(args.db, args.output)
        print(f'OK: {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)')
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
