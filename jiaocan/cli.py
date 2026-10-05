import argparse
import json
import sqlite3
import sys
from .core import BOOKS, connect, normalize, ordered_docs, search, translations


def positive(value):
    n = int(value)
    if n < 1: raise argparse.ArgumentTypeError('必须为正整数')
    return n


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--db', help='SQLite 路径，也可设置 FLOWUS_DB')
    common.add_argument('--json', action='store_true', help='输出结构化结果及来源')
    common.add_argument('--limit', type=positive, help='每页条数（搜索/正文默认 8；目录默认全部）')
    common.add_argument('--page', type=positive, default=1)
    common.add_argument('--all-books', action='store_true', help='指定册无结果时显式跨册查找')
    opts, remaining = common.parse_known_args(argv)
    parser = argparse.ArgumentParser(description='高中语文教参查询（纯标准库）', parents=[common])
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('search'); p.add_argument('keywords', nargs='+'); p.add_argument('--book', choices=BOOKS)
    p = subs.add_parser('book'); p.add_argument('book', choices=BOOKS)
    for cmd in ('unit', 'get', 'text', 'translation'):
        p = subs.add_parser(cmd); p.add_argument('book', choices=BOOKS); p.add_argument('keyword')
    p = subs.add_parser('list-ke'); p.add_argument('keyword', nargs='?', default='')
    args = parser.parse_args(remaining)
    try:
        conn = connect(opts.db)
        try: docs = ordered_docs(conn)
        finally: conn.close()
        rows, notice = [], ''
        cmd = args.command
        if cmd == 'search': rows = search(docs, ' '.join(args.keywords), args.book)
        elif cmd == 'book': rows = [r for r in docs if r['book'] == args.book and r['depth'] == 2]
        elif cmd == 'unit': rows = [r for r in docs if r['book'] == args.book and args.keyword in r['unit'] and r['depth'] >= 3]
        elif cmd == 'list-ke': rows = [r for r in docs if '/课文解说/' in r['path'] and args.keyword in (r['book'] + r['path'])]
        else:
            pool = translations(docs) if cmd == 'translation' else docs
            if cmd == 'text': pool = [r for r in pool if '/课文解说/' in r['path']]
            q = normalize(args.keyword)
            def match(r): return q in normalize(r['title']) or (cmd == 'get' and args.keyword in r['path'])
            rows = [r for r in pool if r['book'] == args.book and match(r)]
            if not rows and opts.all_books:
                rows = [r for r in pool if match(r)]
                if rows: notice = '指定册未命中，以下为显式跨册查询结果；请核对册名。'
            rows.sort(key=lambda r: normalize(r['title']) != q)
        total = len(rows)
        limit = opts.limit or (max(total, 1) if cmd in ('book', 'unit', 'list-ke') else 8)
        start = (opts.page-1)*limit
        results = rows[start:start+limit]
        public_results = results
        if cmd in ('search', 'book', 'unit', 'list-ke'):
            public_results = [dict({k:v for k,v in r.items() if k != 'content'}, content_length=len(r['content'])) for r in results]
        payload = dict(command=cmd, total=total, returned=len(results), page=opts.page, limit=limit, notice=notice, results=public_results)
        if opts.json: print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if notice: print(notice)
            print(f'共命中 {total} 条，本页 {len(results)} 条（第 {opts.page} 页）')
            for r in results:
                print(f"═══ [{r['book']}] {r['path']} ═══")
                if r['subsection']: print(f"小节：{r['subsection']}（源文第 {r['start_line']}–{r['end_line']} 行）")
                if cmd == 'search': print(r['snippet'])
                elif cmd in ('get','text','translation'): print(r['content'])
                else: print(f"{r['title']}（{len(r['content'])} 字）")
            if not total: print('未找到匹配内容；请核对册名和关键词，或使用 search 全库搜索。')
        return 0
    except (ValueError, sqlite3.Error, OSError) as exc:
        if opts.json: print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        else: print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
