"""Materialize only preregistered test rows with the unchanged pilot adapter."""
import hashlib
from .artifacts import *
from .adapter import project,RUNTIME_FIELDS

def prepare():
 from .runner import verify_frozen
 verify_frozen();ensure();assert not (ROOT/'local/runtime_inputs.jsonl').exists();selected=rows(ROOT/'local/selected_originals.jsonl');manifest=read(ROOT/'SAMPLE_MANIFEST.json');assert len(selected)==manifest['N_selected']
 for s in selected:
  p=s['paper'];public={'question':s['question']['question'],**{k:p[k] for k in RUNTIME_FIELDS if k!='question'}};r=project(public);r['runtime_index']=s['runtime_index'];append(ROOT/'local/runtime_inputs.jsonl',r);safe={k:v for k,v in r.items() if k not in {'case','paragraph_mapping','mapping','query_context'}};safe['question_sha256']=hashlib.sha256(public['question'].encode()).hexdigest();safe['runtime_sha256']=hashlib.sha256(canonical(r).encode()).hexdigest();append(ROOT/'RUNTIME_INPUTS.jsonl',safe)
 write(ROOT/'RUN_MANIFEST.json',{'source_test_sha256':read(ROOT/'SOURCE_PROVENANCE.json')['test_member']['sha256'],'code_manifest_sha256':sha(ROOT/'EXPERIMENT_MANIFEST.json'),'sample_manifest_sha256':sha(ROOT/'SAMPLE_MANIFEST.json'),'eligibility_counts_sha256':sha(ROOT/'QASPER_ELIGIBILITY_COUNTS.json'),'runtime_inputs_sha256':sha(ROOT/'local/runtime_inputs.jsonl'),'public_runtime_metadata_sha256':sha(ROOT/'RUNTIME_INPUTS.jsonl'),'selected_originals_sha256':sha(ROOT/'local/selected_originals.jsonl'),'N_selected':len(selected),'all_hashes_before_API':True})
 print('RUNTIME PREPARED',len(selected),'whole papers',sum(r['retrieval_method']=='WHOLE_PAPER' for r in rows(ROOT/'RUNTIME_INPUTS.jsonl')))
if __name__=='__main__':prepare()
