"""Reproducible synthetic fixture evaluation through the installed CLI."""
import json
from pathlib import Path
import subprocess
import sys

example = Path(__file__).resolve().parents[1] / 'examples'
root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('reports').resolve()
root.mkdir(parents=True, exist_ok=True)

def cli(*args, expected=0):
    p = subprocess.run([sys.executable, '-m', 'promptgit', '--store', str(root/'store'), *map(str,args)], text=True, capture_output=True)
    if p.returncode != expected:
        raise RuntimeError(p.stderr + p.stdout)
    return p.stdout.strip()

base = cli('snapshot','--prompt',example/'baseline.txt','--suite',example/'suite.json')
candidate = cli('snapshot','--prompt',example/'candidate.txt','--suite',example/'suite.json','--parent',base)
a = cli('record','--snapshot',base,'--model','synthetic-baseline','--outputs',example/'baseline.json')
b = cli('record','--snapshot',candidate,'--model','synthetic-candidate','--outputs',example/'candidate.json')
cli('diff',a,b,'--format','json','--output',root/'report.json',expected=1)
cli('diff',a,b,'--output',root/'report.md',expected=1)
report = json.loads((root/'report.json').read_text())
assert report['regressions'] == ['classification', 'refund']
assert report['cases'][0]['json_changes'] == [{'path':'/category','change':'replaced','before':'account','after':'billing'}]
assert report['cases'][1]['candidate']['score'] == 1/3
cli('diff',a,a)
(root/'ids.json').write_text(json.dumps({'base':a,'candidate':b},indent=2)+'\n')
print(json.dumps({'base':a,'candidate':b,'regressions':report['regressions'],'report':str(root/'report.md')}))
