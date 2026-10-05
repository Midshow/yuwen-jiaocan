import contextlib
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jiaocan.core import connect, database_path, ordered_docs, search, translations, related, normalize
from jiaocan.cli import main as cli
from flowus_build_db import create_schema, build_book, validate_database, main as build_main
from gen_html_reader import build as build_html
from scripts.build_skill import build as build_skill


def row(uid, title, content='', book='必修上册', unit='第一单元', section='课文解说', parent='root', depth=4, order=0):
    return dict(uuid=uid, book=book, parent_id=parent, type=0, title=title, content=content, depth=depth, ord=order,
                path=f'{book}/{unit}/{section}/{title}')


def write_db(path, rows):
    conn=sqlite3.connect(path); create_schema(conn)
    conn.executemany('INSERT INTO docs VALUES (:uuid,:book,:parent_id,:type,:title,:content,:depth,:ord,:path)', rows)
    conn.commit(); conn.close()


def run_cli(args):
    out=io.StringIO()
    with contextlib.redirect_stdout(out): code=cli(args+['--json'])
    return code,json.loads(out.getvalue())


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'库.db'
        rows=[row('exact','10.1劝学','短解读'),row('title','劝学背景','更多'),row('other','百合花','劝学'*1000),
              row('lower','劝学',book='必修下册'),row('literal','100%_字面','特殊关键词')]
        rows += [row(f'm{i}',f'资料{i}','劝学 主题') for i in range(12)]
        write_db(self.db,rows)
        c=connect(self.db)
        try:self.docs=ordered_docs(c)
        finally:c.close()

    def call(self,*args):return run_cli([*args,'--db',str(self.db)])
    def test_exact_title_before_long_content(self):
        rows=search(self.docs,'劝学','必修上册')
        self.assertEqual([r['uuid'] for r in rows[:2]],['exact','title'])
    def test_total_and_page(self):
        _,a=self.call('search','劝学','--limit','3')
        _,b=self.call('search','劝学','--limit','3','--page','2')
        self.assertEqual(a['total'],16); self.assertEqual(a['returned'],3)
        self.assertFalse({r['doc_id'] for r in a['results']} & {r['doc_id'] for r in b['results']})
        self.assertNotIn('content',a['results'][0]); self.assertIn('snippet',a['results'][0])
    def test_multitoken_and_literal_wildcards(self):
        self.assertEqual(len(search(self.docs,'劝学 主题')),12)
        self.assertEqual(len(search(self.docs,'%_')),1)
    def test_wrong_book_does_not_fallback(self):
        _,a=self.call('get','必修下册','百合花'); self.assertEqual(a['total'],0)
        _,b=self.call('get','必修下册','百合花','--all-books')
        self.assertEqual(b['total'],1); self.assertIn('跨册',b['notice'])
    def test_missing_database_is_not_created(self):
        missing=self.db.parent/'missing.db'
        code,result=run_cli(['search','劝学','--db',str(missing)])
        self.assertEqual(code,2); self.assertIn('--db',result['error']); self.assertFalse(missing.exists())
    def test_invalid_database(self):
        bad=self.db.parent/'bad.db';bad.write_bytes(b'not sqlite')
        code,result=run_cli(['search','劝学','--db',str(bad)])
        self.assertEqual(code,2); self.assertIn('格式无效',result['error'])
    def test_readonly(self):
        c=connect(self.db)
        try:
            with self.assertRaises(sqlite3.OperationalError):c.execute('DELETE FROM docs')
        finally:c.close()
    def test_environment_precedence(self):
        with patch.dict(os.environ,{'FLOWUS_DB':str(self.db),'FLOWUS_DATA_DIR':'elsewhere'}):
            self.assertEqual(database_path(),self.db.resolve())
            self.assertEqual(database_path(self.db.parent/'explicit.db'),(self.db.parent/'explicit.db').resolve())
    def test_invalid_limit(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            cli(['search','劝学','--limit','0'])
        self.assertEqual(exc.exception.code,2)


class TranslationTests(unittest.TestCase):
    def test_section_boundaries_and_source_lines(self):
        r=row('source','资料链接','背景\n二、文言文参考译文\n1.《赤壁赋》\n甲译文\n乙译文\n2.《登泰山记》\n丙译文\n三、赏析\n不应入译文')
        r.update(doc_id='source',unit='第一单元',section='资料链接')
        a,b=translations([r])
        self.assertEqual(a['content'],'甲译文\n乙译文');self.assertEqual(b['content'],'丙译文')
        self.assertEqual((a['start_line'],a['end_line']),(3,5))
        self.assertEqual(a['doc_id'],'source')
    def test_inline_translation_and_single_named_section(self):
        a=row('inline','劝学','分析\n《劝学》译文\n译文内容\n二、练习\n练习')
        b=row('single','资料链接','一、《促织》参考译文\n另一译文\n二、背景\n背景')
        for r in (a,b):r.update(doc_id=r['uuid'])
        trs=translations([a,b]);self.assertEqual([r['content'] for r in trs],['译文内容','另一译文'])
    def test_no_translation_from_publisher_or_prose_mentions(self):
        a=row('a','背景','上海译文出版社\n作者比较了两种译文。');a['doc_id']='a'
        self.assertEqual(translations([a]),[])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
    def node(self,uid,title,kind=0,children=None):
        return dict(type=kind,parentId=None,data={'segments':[{'text':title}]},subNodes=children or [])
    def tree(self):
        return {'root':{'root':self.node('root','必修上册',children=['container','second']),
                        'container':self.node('container','容器',38,['page']), 'second':self.node('second','第二单元')},
                'container':{'page':self.node('page','第一单元',children=['text'])},
                'page':{'text':self.node('text','正文',1)}, 'second':{}}
    def save(self,tree):
        (self.folder/'必修上册_tree.json').write_text(json.dumps(tree,ensure_ascii=False),encoding='utf-8')
    def test_nested_page_preserved_in_document_order(self):
        self.save(self.tree());c=sqlite3.connect(':memory:');create_schema(c);report={}
        try:
            self.assertEqual(build_book('必修上册','root',c,self.folder,report),3)
            self.assertEqual(c.execute("SELECT parent_id,content,ord,depth FROM docs WHERE uuid='page'").fetchone(),('root','正文',0,2))
            self.assertEqual(c.execute("SELECT ord FROM docs WHERE uuid='second'").fetchone()[0],1)
            self.assertEqual(validate_database(c)['orphan_nodes'],[])
        finally:c.close()
    def test_missing_block_is_failure(self):
        tree=self.tree();tree['page']={};self.save(tree)
        c=sqlite3.connect(':memory:');create_schema(c)
        try:
            with self.assertRaisesRegex(ValueError,'缺失块'):build_book('必修上册','root',c,self.folder)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM docs').fetchone()[0],0)
        finally:c.close()
    def test_unreachable_page_is_failure(self):
        tree=self.tree();tree['lost']={'lost':self.node('lost','失联页')};self.save(tree)
        c=sqlite3.connect(':memory:');create_schema(c)
        try:
            with self.assertRaisesRegex(ValueError,'未遍历子页'):build_book('必修上册','root',c,self.folder)
        finally:c.close()
    def test_conflicting_duplicate_id_rejected(self):
        tree=self.tree();tree['second']['page']=self.node('page','冲突名称');self.save(tree)
        c=sqlite3.connect(':memory:');create_schema(c)
        try:
            with self.assertRaisesRegex(ValueError,'重复节点'):build_book('必修上册','root',c,self.folder)
        finally:c.close()
    def test_failed_rebuild_preserves_existing_database(self):
        target=self.folder/'original.db';write_db(target,[row('original','原有内容')]);before=target.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            code=build_main(['--data-dir',str(self.folder),'--db',str(target),'--report',str(self.folder/'report.json')])
        self.assertEqual(code,2);self.assertEqual(target.read_bytes(),before)
        self.assertIn('error',json.loads((self.folder/'report.json').read_text(encoding='utf-8')))
    def test_parent_order_before_child_local_order(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;create_schema(c)
        rows=[row('r','册',depth=1,parent=None),row('u1','一',depth=2,parent='r',order=0),row('u2','二',depth=2,parent='r',order=1),row('c1','末篇',parent='u1',order=10),row('c2','首篇',parent='u2',order=0)]
        c.executemany('INSERT INTO docs VALUES (:uuid,:book,:parent_id,:type,:title,:content,:depth,:ord,:path)',rows)
        try:self.assertEqual([r['uuid'] for r in ordered_docs(c)],['r','u1','c1','u2','c2'])
        finally:c.close()


class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn=connect()
        try:cls.docs=ordered_docs(conn)
        finally:conn.close()
        cls.trs=translations(cls.docs)
    def test_baseline_counts_and_integrity(self):
        self.assertEqual(len(self.docs),282)
        self.assertEqual(sum('/课文解说/' in d['path'] for d in self.docs),116)
        c=connect()
        try:
            report=validate_database(c);self.assertEqual(report['integrity'],'ok');self.assertEqual(report['orphan_nodes'],[]);self.assertEqual(report['duplicate_paths'],[])
        finally:c.close()
    def test_representative_translations_all_five_books(self):
        for title,book in [('赤壁赋','必修上册'),('劝学','必修上册'),('师说','必修上册'),('侍坐','必修下册'),('促织','必修下册'),('大学之道','选择性必修上册'),('苏武传','选择性必修中册'),('陈情表','选择性必修下册')]:
            with self.subTest(title=title):
                code,result=run_cli(['translation',book,title]);self.assertEqual(code,0);self.assertGreater(result['total'],0)
                self.assertTrue(all(len(r['content'])>50 for r in result['results']))
    def test_translation_exact_source_slices(self):
        sources={d['doc_id']:d for d in self.docs}
        self.assertGreater(len(self.trs),20)
        for tr in self.trs:
            lines=sources[tr['doc_id']]['content'].splitlines()
            self.assertEqual(tr['content'],'\n'.join(lines[tr['start_line']:tr['end_line']]).strip())
    def test_all_translation_sources_link_to_lessons(self):
        lessons=[d for d in self.docs if '/课文解说/' in d['path']]
        linked={t['translation_id'] for d in lessons for t in related(self.docs,d,self.trs)['translations']}
        self.assertEqual(linked,{t['translation_id'] for t in self.trs})
        self.assertEqual(len(self.trs),35)
        self.assertEqual(len({(t['book'],normalize(t['title'])) for t in self.trs}),32)
    def test_red_cliff_links(self):
        lesson=next(d for d in self.docs if '/课文解说/' in d['path'] and normalize(d['title'])=='赤壁赋')
        links=related(self.docs,lesson,self.trs)
        self.assertTrue(links['translations']);self.assertTrue(links['tasks']);self.assertTrue(links['materials'])
        self.assertNotIn('泰山的南面',links['translations'][0]['content'])
    def test_full_listing_default(self):
        _,result=run_cli(['list-ke']);self.assertEqual(result['returned'],116)
    def test_portable_skill_in_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);archive=build_skill(folder/'skill.zip')
            with zipfile.ZipFile(archive) as z:z.extractall(folder/'installed')
            skill=folder/'installed/gaozhong-yuwen-jiaocan'
            manifest=json.loads((skill/'manifest.json').read_text(encoding='utf-8'))
            for name,sha in manifest['sha256'].items():self.assertEqual(hashlib.sha256((skill/name).read_bytes()).hexdigest(),sha)
            env={k:v for k,v in os.environ.items() if k not in ('FLOWUS_DB','FLOWUS_DATA_DIR')};env['PYTHONIOENCODING']='utf-8'
            result=subprocess.run([sys.executable,str(skill/'scripts/flowus_query.py'),'translation','必修上册','赤壁赋','--json'],cwd=folder,env=env,capture_output=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['total'],1)
    def test_html_source_links_and_safe_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);db=p/'test.db'
            write_db(db,[row('x','恶意标题','</script><script>alert(1)</script>')])
            output=build_html(db,p/'nested'/'reader.html').read_text(encoding='utf-8')
            self.assertNotIn('</script><script>alert(1)',output)
            data=json.loads(output.split('<script id="library-data" type="application/json">')[1].split('</script>')[0])
            self.assertEqual(data['docs'][0]['content'],'</script><script>alert(1)</script>')


if __name__ == '__main__':unittest.main()
