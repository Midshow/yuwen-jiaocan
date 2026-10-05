"""Create a complete portable skill ZIP, including its database and shared engine."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jiaocan.core import connect, database_path


def build(output, db=None):
    source_db = database_path(db)
    conn = connect(source_db)
    try:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('数据库完整性检查失败')
    finally:
        conn.close()
    files = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / 'jiaocan').glob('*.py')}
    files.update({p.relative_to(ROOT).as_posix(): p for p in (ROOT / 'references').glob('*.md')})
    for name in ('SKILL.md', 'LICENSE', 'flowus_query.py', 'scripts/flowus_query.py'):
        files[name] = ROOT / name
    files['flowus_data/高中语文教参.db'] = source_db
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in [p.resolve() for p in files.values()]:
        raise ValueError('输出 ZIP 不能覆盖输入文件')
    prefix = 'gaozhong-yuwen-jiaocan/'
    manifest = {}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            data = path.read_bytes()
            archive.writestr(prefix + name, data)
            manifest[name] = hashlib.sha256(data).hexdigest()
        archive.writestr(prefix + 'manifest.json', json.dumps({'sha256': manifest}, ensure_ascii=False, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db'); parser.add_argument('--output', default=str(ROOT / 'dist/gaozhong-yuwen-jiaocan.zip'))
    args = parser.parse_args()
    try:
        print(build(args.output, args.db)); return 0
    except (OSError, ValueError) as exc:
        print(f'错误：{exc}', file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
