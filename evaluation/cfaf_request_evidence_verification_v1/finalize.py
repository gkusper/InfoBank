"""Final byte inventory, secret scan and prior-history guard before local commit."""
import hashlib,os,subprocess
from .artifacts import *
from .runner import verify_frozen

def finalize():
 verify_frozen();state=read(ROOT/'task_state.json')
 changed=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h]
 if changed:raise RuntimeError('Protected historical files changed: '+repr(changed))
 prefix=ROOT.relative_to(REPO).as_posix();names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--',prefix],cwd=REPO,text=True).splitlines()
 names=sorted(set(names)|{prefix+'/CHANGED_FILES.txt',prefix+'/checksums.sha256',prefix+'/finalize.py'})
 (ROOT/'CHANGED_FILES.txt').write_text('\n'.join(names)+'\n',encoding='utf-8')
 secret=os.getenv('OPENAI_API_KEY');payload=[]
 for name in names:
  path=REPO/name
  if not path.exists():raise RuntimeError('Missing deliverable: '+name)
  raw=path.read_bytes()
  if secret and secret.encode() in raw:raise RuntimeError('Secret scan failed')
  if name!=prefix+'/checksums.sha256':payload.append(hashlib.sha256(raw).hexdigest()+'  '+name)
 (ROOT/'checksums.sha256').write_text('\n'.join(payload)+'\n',encoding='utf-8')
 for line in payload:
  digest,name=line.split('  ',1)
  if sha(REPO/name)!=digest:raise RuntimeError('Checksum mismatch: '+name)
 print({'new_files':len(names),'checksums':len(payload),'protected_prior_files_unchanged':len(state['protected_files']),'secret_scan':'PASS','frozen_runtime':'UNCHANGED'})
if __name__=='__main__':finalize()
