"""Same exposed development inputs; no new corpus or reserved group opened."""
import copy,hashlib,json
from .artifacts import *
from .deadline import ensure
from . import integration as impl
from .integration_controls import assess
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
CONFIGS=['A0','B3','T1','T2','T3']

def prepare():
 ensure('target/claim cached ablation',90)
 if (ROOT/'cached_ablation.jsonl').exists():raise RuntimeError('Already prepared')
 source=REPO/'evaluation/cfaf_requirement_alignment_v1';old=rows(source/'cached_ablation_final.jsonl');ledger_path=REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json';ledger=read(ledger_path);known={r['id'] for r in ledger['entries']};results=[]
 for record in old:
  directory=REPO/record['raw_source'];i=record['origin_index'];out=rows(directory)[i]['outcome'];case=rows(directory.parent/'selected_cases.jsonl')[i];assert case['id'] in known
  runtime=public_case({'perturbed_query':case['perturbed_query'],'perturbed_context':case['perturbed_context']},i);request=request_for(runtime,out);a,data,audit=impl.parse_analysis(json.dumps(out['semantic_assessment']),request);assert a.valid;before=canonical(data);provenance=trusted_provenance(request,False)
  variants={c:assess(request,a,data,c,provenance) for c in CONFIGS};pred={c:selector(v,request,data) for c,v in variants.items()};assert pred['A0']==record['predictions']['A0'] and pred['B3']==record['predictions']['B3'];assert all(pred[c]==pred['B3'] for c in ['T1','T2','T3']);assert canonical(data)==before
  row={'index':len(results),'origin':record['origin'],'origin_index':i,'raw_source':record['raw_source'],'expected_mode':record['expected_mode'],'expected_label':record['expected_label'],'predictions':pred,'results':variants,'semantic_assessment_sha256':hashlib.sha256(before.encode()).hexdigest(),'upstream_unchanged':True,'api_calls':0};append(ROOT/'cached_ablation.jsonl',row);results.append(row)
 for name in ['pilot_runtime.jsonl','pilot_scorer_only.jsonl']:(ROOT/name).write_bytes((source/name).read_bytes())
 old_selection=read(source/'selection_manifest.json');write(ROOT/'selection_manifest.json',{**old_selection,'selection_policy':'Exact 24-case mixed InfoBank/RefusalBench subset from the immediately preceding RDA experiment; no new records.','runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'source_runtime_sha256':sha(source/'pilot_runtime.jsonl'),'source_commit':read(ROOT/'task_state.json')['baseline_commit'],'exposure_ledger_sha256':sha(ledger_path),'new_exposures':0,'cached_count':len(results)})
 for c in CONFIGS:print(c,sum(r['predictions'][c]==r['expected_mode'] for r in results),'/',len(results))
 print('Prepared cached40 and unchanged pilot24; zero new exposure')
if __name__=='__main__':prepare()
