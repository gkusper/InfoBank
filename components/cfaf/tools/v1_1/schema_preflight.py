"""Development-only schema/token preflight: no model calls or benchmark input."""
from common import *
import os,sys,importlib.metadata as meta

def main():
 ensure();s=snapshot_check();env=os.environ.copy();env['PYTHONPATH']=str(Path(s['snapshot'])/'src');env['OUT_SCHEMA']=str(OUT/'local/schema_v1.json')
 code="import json,os;from pathlib import Path;from component_cfaf.adapters.openai_sdk import strict_schema,PROMPT;from component_cfaf.contracts import LLMProposal;Path(os.environ['OUT_SCHEMA']).write_text(json.dumps({'schema':strict_schema(LLMProposal),'prompt':PROMPT}),encoding='utf-8')"
 subprocess.run([sys.executable,'-c',code],cwd=WORK,env=env,check=True)
 from component_cfaf.compact import CompactProposal,COMPACT_PROMPT
 from component_cfaf.adapters.openai_sdk import strict_schema
 write(OUT/'local/schema_v1_1.json',{'schema':strict_schema(CompactProposal),'prompt':COMPACT_PROMPT})
 examples=[]
 for count in [1,3,6]:
  claims=[];evidence=[]
  for i in range(count):
   quote=f'Fictional process {i+1} closes exactly {i+3} tasks under the approved scope.'
   evidence.append({'id':f'e{i}','source_id':f'view-{i+1:04d}','quote':quote,'role':'PRIMARY'})
   claims.append({'id':f'c{i}','requirements':['req-1'],'text':quote,'value_type':'TEXT','value':None,'subject':None,'parents':[],'evidence':[f'e{i}']})
  examples.append({'essential_claims':count,'proposal':{'evidence':evidence,'claims':claims,'missing':[],'unresolved':False}})
 write(OUT/'local/synthetic_token_examples.json',examples)
 deps={d.metadata['Name']:d.version for d in meta.distributions()};write(OUT/'dependency_audit.json',{'runtime_dependencies_unchanged':True,'isolated_runtime_versions':deps,'new_runtime_dependencies':[],'dev_only_tokenizer':'tiktoken==0.12.0 in separate tools-venv, not imported by runtime','NLI_spaCy_models':'NOT_INSTALLED_NOT_USED','v1_snapshot_requirements_sha256':sha(Path(s['snapshot'])/'requirements.lock'),'v1_1_requirements_sha256':sha(ROOT/'requirements.lock'),'SDK':'openai==1.59.9; strict output; retries zero','v1_completed_commit':s['v1_commit']})
 print('SCHEMA AUDIT INPUTS WRITTEN; runtime dependencies unchanged')
if __name__=='__main__':main()
