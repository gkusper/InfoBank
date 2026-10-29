import json,hashlib,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT.parents[1]
OUT=ROOT/'results/v1_1'
WORK=REPO.parents[1]/'work/component-cfaf-v1_1'
STATE=WORK/'state.json'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
def append(p,v):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n');f.flush()
def ensure(api=False):
 s=read(STATE);elapsed=max(time.time()-s['start_epoch'],time.monotonic()-s['monotonic_start_estimate'])
 if elapsed>=(6300 if api else 7200):raise RuntimeError('TASK_TIME_BOUND')
 return elapsed
def snapshot_check():
 s=read(STATE);snap=Path(s['snapshot']);assert all(sha(snap/p)==h for p,h in s['snapshot_hashes'].items());assert all(sha(REPO/p)==h for p,h in s['original_v1_private'].items());return s

def verify_freeze():
 f=read(OUT/'experiment_manifest.json')
 for p,h in f['source_files'].items():assert sha(ROOT/p)==h,'FROZEN_SOURCE_CHANGED:'+p
 assert sha(ROOT/'results/local/inputs.jsonl')==f['inputs_sha256'];assert sha(ROOT/'results/local/gold.jsonl')==f['gold_sha256'];snapshot_check();return f
