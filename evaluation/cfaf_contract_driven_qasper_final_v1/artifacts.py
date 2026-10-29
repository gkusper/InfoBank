"""Version-local artifact helpers."""
import json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def append(p,v):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n');f.flush()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'))
def ensure(new_api=False):
 s=read(ROOT/'task_state.json');elapsed=time.time()-s['start_epoch'];limit=s['new_api_stop_seconds'] if new_api else s['hard_limit_seconds']
 if elapsed>=limit:raise RuntimeError('TASK_TIME_BOUND_EXHAUSTED')
 return elapsed
