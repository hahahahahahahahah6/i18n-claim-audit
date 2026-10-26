import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from i18n_claim_audit.core import audit, I18N, NOI18N
from i18n_claim_audit.cli import main
ROOT = Path(__file__).resolve().parents[1]

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def put(self, name, value=''):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value, encoding='utf-8')
    def runcli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = main([str(self.root)] + list(args))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()
    def positive(self):
        self.put('README.md', 'supports multiple languages')
    def bad(self):
        self.assertEqual(self.runcli()[0], 2)
        self.assertEqual(audit(self.root)['findings'], [{'rule':'documented-i18n-claim-false','severity':'HIGH','path':'README.md'}])
    def test_01_evidence(self):
        self.positive()
        for name, value in [('a.py','from gettext import gettext as _\n_("hi")'),('a.py','from gettext import gettext\ngettext("hi")'),('a.py','import gettext as gt\ngt.translation("app")'),('a.py','import babel\nbabel.Locale("fr")'),('a.py','from babel.dates import format_date as f\nf()'),('a.py','from fluent.runtime import FluentBundle as B\nB()'),('a.py','from PySide6.QtCore import QTranslator as T\nt=T()\napp.installTranslator(t)'),('fr.po',''),('fr.mo',''),('locales/fr.json','{"a":"b"}'),('lang/fr.json','{"a":{"b":"c"}}')]:
            with self.subTest(value=value):
                self.put(name,value)
                self.assertEqual(self.runcli()[0],0)
                self.assertTrue(audit(self.root)['evidence'])
                (self.root/name).unlink()
    def test_02_bad(self):
        self.positive()
        self.put('a.py','print("hi")')
        self.bad()
        self.assertEqual(self.runcli()[1],'FAIL\ndocumented-i18n-claim-false HIGH\n')
    def test_03_negative(self):
        self.put('README.md','no translations')
        self.put('fr.po')
        self.assertEqual(audit(self.root)['findings'],[{'rule':'documented-no-i18n-claim-false','severity':'HIGH','path':'README.md'}])
        self.assertEqual(self.runcli()[0],2)
    def test_04_nosource(self):
        self.positive()
        self.bad()
        self.put('README.md','english only')
        self.assertEqual(self.runcli()[0],0)
    def test_05_markdown(self):
        for value,count in [('```\nlocalized\n```',0),('~~~text\nlocalized\n~~~',0),('`localized`',1),('supports multiple\nlanguages',1),('supports multiple\n\nlanguages',0)]:
            self.put('README.md',value)
            self.assertEqual(len(audit(self.root)['claims']),count)
    def test_06_negation(self):
        for value in NOI18N:
            with self.subTest(value=value):
                self.put('README.md',value)
                self.assertEqual(audit(self.root)['claims'],[{'family':'noi18n','path':'README.md'}])
                self.assertEqual(self.runcli()[0],0)
                self.put('fr.po')
                self.assertEqual(audit(self.root)['findings'][0]['rule'],'documented-no-i18n-claim-false')
                (self.root/'fr.po').unlink()
    def test_07_nouns_and_templates(self):
        for value in ['the translation was slow','languages are hard','i18n locale translations','unlocalized']:
            self.put('README.md',value)
            self.assertEqual(audit(self.root)['claims'],[])
        for value in I18N:
            self.put('README.md',value.upper().replace(' ','-'))
            self.bad()
    def test_08_non_evidence(self):
        self.positive()
        for name,value in [('a.py','import gettext'),('a.py','import babel'),('a.py','from django.utils.translation import gettext'),('a.py','_("hi")'),('a.py','gettext("hi")'),('a.py','import locale\nlocale.setlocale(0, "")'),('a.py','translations={"hi":"salut"}'),('tests/fr.po',''),('tests/locales/fr.json','{"a":"b"}'),('fr.json','{"a":"b"}'),('locale/fr.json','{"a":1}'),('locale/fr.json','[]'),('locale/fr.json','invalid'),('locale/fr.json','{"a":{"b":{"c":"deep"}}}'),('a.py','b"hi".decode("utf-8")'),('a.py','open("x", encoding="utf-8")\nb"hi".decode("utf-8")'),('a.py','# gettext.install()\n"gettext.gettext()"'),('test_a.py','import gettext\ngettext.install()')]:
            with self.subTest(value=value):
                self.put(name,value)
                self.bad()
                (self.root/name).unlink()
        self.put('a.py','import gettext')
        self.put('b.py','gettext.gettext("hi")')
        self.bad()
    def test_09_medium(self):
        self.put('tests/docs/a.md','localized')
        self.assertEqual(audit(self.root)['findings'][0]['severity'],'MEDIUM')
        self.assertEqual(self.runcli()[0],2)
        code,out=self.runcli('--fail-on','HIGH')
        self.assertEqual(code,0)
        self.assertIn('MEDIUM',out)
    def test_10_priority(self):
        for name in ['tests/docs/a.md','docs/b.md','docs/a.md']:
            self.put(name,'localized')
        f=audit(self.root)['findings']
        self.assertEqual(len(f),1)
        self.assertEqual((f[0]['severity'],f[0]['path']),('HIGH','docs/a.md'))
    def test_11_cli(self):
        self.positive()
        self.assertEqual(set(json.loads(self.runcli('--json')[1])),{'status','evidence','claims','findings'})
        self.assertIn('README.md',self.runcli('--verbose')[1])
        self.assertEqual(self.runcli('--ignore','README.*')[0],0)
        self.put('fr.po')
        self.assertEqual(self.runcli('--ignore','*.po')[0],2)
        self.assertEqual(self.runcli('--version'),(0,'0.1.0\n'))
        self.assertEqual(self.runcli('--unknown')[0],1)
        self.assertEqual(self.runcli('--fail-on','LOW')[0],1)
        self.assertEqual(self.runcli(str(self.root/'missing'))[0],1)
        p=subprocess.run([sys.executable,'-m','i18n_claim_audit','--version'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual((p.returncode,p.stdout),(0,'0.1.0\n'))
        # Installed console script is exercised in both distribution checks.
        self.assertIn('i18n_claim_audit.cli:main',(ROOT/'pyproject.toml').read_text())
    def test_12_self(self):
        result=audit(ROOT)
        self.assertEqual((result['status'],result['claims']),('PASS',[]))
    def test_13_env(self):
        marker='ENV_GUARD_MARKER localized'
        self.put('.env',marker)
        original=Path.open
        def guarded(path,*args,**kwargs):
            self.assertNotEqual(path.name,'.env')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',guarded):
            code,out=self.runcli('--json')
        self.assertEqual(code,0)
        self.assertNotIn(marker,out)
    def test_errors_and_symlinks(self):
        self.put('a.py','def (')
        self.assertEqual(self.runcli()[0],1)
        (self.root/'a.py').unlink()
        self.positive()
        (self.root/'fr.po').symlink_to(ROOT/'LICENSE')
        (self.root/'loop').symlink_to(self.root,target_is_directory=True)
        self.bad()
        original=Path.read_text
        def denied(path,*args,**kwargs):
            if path.name=='README.md':
                raise PermissionError('unreadable fixture')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',denied):
            self.assertEqual(self.runcli()[0],1)
