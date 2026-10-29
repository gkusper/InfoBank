"""Local experiment helpers. No benchmark code is imported by package runtime."""
import json,hashlib,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
WORK=REPO.parents[1]/'work/component-cfaf-v1'
STATE=WORK/'state.json'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def append(p,v):
    with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n');f.flush()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ensure(new_api=False):
    state=read(STATE);elapsed=max(time.time()-state['start_epoch'],time.monotonic()-state.get('monotonic_start_estimate',time.monotonic()))
    if elapsed>=(6300 if new_api else 7200):raise RuntimeError('TASK_TIME_BOUND')
    return elapsed
def git_json(path):return json.loads(subprocess.check_output(['git','show',read(STATE)['base']+':'+path],cwd=REPO).decode('utf-8-sig'))
def verify_freeze():
    f=read(ROOT/'results/freeze.json')
    for p,h in f['files'].items():assert sha(ROOT/p)==h,'FROZEN_FILE_CHANGED:'+p
    assert sha(ROOT/'results/local/inputs.jsonl')==f['inputs_sha256']
    assert sha(ROOT/'results/local/gold.jsonl')==f['gold_sha256']
    return f
