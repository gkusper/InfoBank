"""Small artifact helpers. Scoring annotations stay outside runtime execution."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def append(path,data):
 with Path(path).open('a',encoding='utf-8') as f:f.write(json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
