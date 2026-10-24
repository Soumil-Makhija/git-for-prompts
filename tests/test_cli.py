import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from promptgit.cli import markdown

ROOT = str(Path(__file__).resolve().parents[1])

class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, data in {'suite.json': {'cases':[{'id':'a','input':'Hello','checks':[{'contains':'hello'}]}]},
                           'a.json':{'a':'hello world'}, 'b.json':{'a':'goodbye'}}.items():
            (self.root/name).write_text(json.dumps(data))
        (self.root/'prompt.txt').write_text('Be helpful')

    def cli(self, *args, code=0):
        env = dict(os.environ, PYTHONPATH=ROOT)
        p = subprocess.run([sys.executable,'-m','promptgit',*args],cwd=self.root,env=env,text=True,capture_output=True)
        self.assertEqual(p.returncode, code, p.stderr+p.stdout)
        return p.stdout.strip()

    def test_full_workflow(self):
        v = self.cli('snapshot','--prompt','prompt.txt','--suite','suite.json')
        a = self.cli('record','--snapshot',v,'--model','baseline','--outputs','a.json')
        (self.root/'prompt.txt').write_text('Be concise')
        w = self.cli('snapshot','--prompt','prompt.txt','--suite','suite.json','--parent',v)
        b = self.cli('record','--snapshot',w,'--model','candidate','--outputs','b.json')
        result = json.loads(self.cli('diff',a,b,'--format','json',code=1))
        self.assertTrue(result['prompt_changed']); self.assertEqual(result['regressions'],['a'])
        self.cli('diff',a,b,'--output','report.md',code=1)
        self.assertIn('-hello world', (self.root/'report.md').read_text())
        self.assertEqual(json.loads(self.cli('show',w,'--kind','snapshot'))['parent'],v)
        self.cli('diff',a,a)
        self.cli('diff',a,b,'--tolerance','1')

    def test_bad_inputs(self):
        self.cli('show','../bad','--kind','run',code=2)
        self.cli('snapshot','--prompt','missing','--suite','suite.json',code=2)
        (self.root/'suite.json').write_text('{"cases":[],"cases":[]}')
        self.cli('snapshot','--prompt','prompt.txt','--suite','suite.json',code=2)

    def test_markdown_untrusted_fence(self):
        from promptgit.core import Store, compare
        s=Store(self.root/'s'); v=s.snapshot('x',{'cases':[{'id':'<x>','input':'x','checks':[{'contains':'ok'}]}]})
        a=s.record(v,'a',{'<x>':'ok'}); b=s.record(v,'b',{'<x>':'```\n<script>oops</script>'})
        text=markdown(compare(s,a,b))
        self.assertIn('````diff',text); self.assertIn('&lt;x&gt;',text)

if __name__ == '__main__': unittest.main()
