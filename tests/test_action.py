import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from promptgit.core import Store

class ActionTests(unittest.TestCase):
    def test_guard_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); s=Store(root/'store')
            v=s.snapshot('p',{'cases':[{'id':'x','input':'x','checks':[{'equals':'ok'}]}]})
            a=s.record(v,'a',{'x':'ok'}); b=s.record(v,'b',{'x':'bad'})
            env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
                     PROMPTGIT_STORE=str(root/'store'),PROMPTGIT_BASE=a,
                     PROMPTGIT_REPORT=str(root/'report.md'),GITHUB_STEP_SUMMARY=str(root/'summary.md'))
            script=Path(__file__).resolve().parents[1]/'scripts/action.py'
            for candidate, expected in [(a,0),(b,1),('bad',2)]:
                env['PROMPTGIT_CANDIDATE']=candidate
                p=subprocess.run([sys.executable,str(script)],env=env,capture_output=True,text=True)
                self.assertEqual(p.returncode,expected,p.stderr)
            summary=(root/'summary.md').read_text()
            self.assertIn('Result: PASS',summary); self.assertIn('Result: FAIL',summary)

    def test_opt_in_publication_with_mock_transport(self):
        import importlib.util
        from unittest.mock import patch
        script=Path(__file__).resolve().parents[1]/'scripts/action.py'
        spec=importlib.util.spec_from_file_location('guard_action',script)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); s=Store(root/'store')
            v=s.snapshot('sensitive',{'cases':[{'id':'@someone','input':'secret','checks':[{'equals':'ok'}]}]})
            a=s.record(v,'a',{'@someone':'ok'}); b=s.record(v,'b',{'@someone':'untrusted secret'})
            event=root/'event.json'; event.write_text('{}')
            env={'PROMPTGIT_STORE':str(root/'store'),'PROMPTGIT_BASE':a,'PROMPTGIT_CANDIDATE':b,
                 'PROMPTGIT_REPORT':str(root/'report.md'),'PROMPTGIT_COMMENT':'true','PROMPTGIT_TOKEN':'fake',
                 'GITHUB_EVENT_NAME':'pull_request','GITHUB_EVENT_PATH':str(event),'GITHUB_REPOSITORY':'owner/repo'}
            with patch.dict(os.environ,env,clear=True), patch.object(module,'publish') as send:
                self.assertEqual(module.run(),1)
                body=send.call_args.args[-1]
                self.assertIn('FAIL',body); self.assertNotIn('secret',body); self.assertNotIn('@someone',body)
                send.side_effect=OSError('simulated endpoint failure')
                self.assertEqual(module.run(),2)
            env['PROMPTGIT_COMMENT']='false'
            with patch.dict(os.environ,env,clear=True), patch.object(module,'publish') as send:
                self.assertEqual(module.run(),1); send.assert_not_called()
