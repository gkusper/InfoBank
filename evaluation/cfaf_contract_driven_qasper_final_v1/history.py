"""Verify and import exact Dataset1/2 results; no model calls or rerun."""
import subprocess,hashlib,json,inspect
from .artifacts import *
from . import measured_c as impl
from .systems import STANDARD_PROMPT,guarded_a
from evaluation.cfaf_contract_driven_2h_v1 import measured_c as original
OLD=REPO/'evaluation/cfaf_contract_driven_2h_v1'
BASE='bfd80bbfe2ccbb251da46bdc22b791dad5b9341f'
def run():
 ensure();assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==BASE;m=read(OLD/'experiment_manifest.json');assert all(sha(REPO/p)==h for p,h in m['frozen_source_sha256'].items())
 verified=[]
 for line in (OLD/'checksums.sha256').read_text(encoding='utf-8-sig').splitlines():
  h,p=line.split('  ',1);assert sha(REPO/p)==h,p;verified.append(p)
 copies={};summary=read(OLD/'comparison_summary.json');selected={}
 for d in ['dataset1','dataset2']:
  records=rows(OLD/(d+'_results.jsonl'));selection=read(OLD/(d+'_selection_manifest.json'));assert len(records)==40;assert [r['runtime_index'] for r in records]==list(range(40));assert all(r['execution_status']=='COMPLETED' and set(r['systems'])=={'A','B','C'} for r in records);assert summary[d]['planned']==summary[d]['paired_executions_completed']==40
  ids=set(selection['case_ids'] if d=='dataset1' else [r['id'] for r in selection['records']]);assert ids=={r['sample_id'] for r in records}
  for oldname,newname in [(d+'_results.jsonl','IMPORTED_'+d.upper()+'_RESULTS.jsonl'),(d+'_selection_manifest.json','IMPORTED_'+d.upper()+'_SELECTION.json')]:
   b=(OLD/oldname).read_bytes();(ROOT/newname).write_bytes(b);copies[newname]={'source':str((OLD/oldname).relative_to(REPO)),'sha256':sha(ROOT/newname),'byte_identical':True}
  selected[d]=summary[d]
 write(ROOT/'IMPORTED_HISTORY_SUMMARY.json',selected)
 assert impl.run_governed is original.run_governed;assert impl.GOVERNED_PROMPT==original.GOVERNED_PROMPT;assert impl.ANALYSIS_SCHEMA==original.ANALYSIS_SCHEMA
 state=read(ROOT/'task_state.json');primary=Path(state['primary_repo']);pilot='evaluation/cfaf_qasper_pilot_v1/adapter.py';blob=subprocess.check_output(['git','show','be8460d073952e61ccd1b912caea88ab01f37eb3:'+pilot],cwd=REPO);assert (ROOT/'adapter.py').read_bytes()==blob
 write(ROOT/'HISTORICAL_IMPORT_AUDIT.json',{'frozen_branch':'experiment/cfaf-contract-driven-v1','frozen_commit':BASE,'old_report_sha256':sha(OLD/'REPORT.md'),'old_manifest_sha256':sha(OLD/'experiment_manifest.json'),'old_checksums_sha256':sha(OLD/'checksums.sha256'),'verified_prior_artifact_count':len(verified),'verified_prior_frozen_source_count':len(m['frozen_source_sha256']),'imported_files':copies,'D1_D2_new_model_calls':0,'exact_A_B_C_algorithm_identity':True,'prompt_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in {'A':STANDARD_PROMPT,'C_analysis':impl.GOVERNED_PROMPT,'C_realization':impl.CFAF_PROMPT}.items()},'schema_sha256':{k:hashlib.sha256(canonical(v).encode()).hexdigest() for k,v in {'analysis':impl.ANALYSIS_SCHEMA,'generation':impl.GENERATION_SCHEMA,'profile':impl.PROFILE_SCHEMA}.items()},'model_settings':{'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':512,'query_profile_max_tokens':500},'pilot_adapter_commit':'be8460d073952e61ccd1b912caea88ab01f37eb3','adapter_exact_text_sha256':hashlib.sha256(blob.decode('utf-8-sig').encode()).hexdigest(),'changes_required_by_dataset':'QASPER one complete paper vs GaRAGe supplied passages, pilot 110000/120000 context envelope vs old 60000; not a perfectly input-controlled combined comparison','algorithm_changes':False,'checkout_line_ending_restoration':state['checkout_line_ending_restoration'],'original_manifests_or_results_changed':False,'ComponentBasaedCFAF_used':False})
 print('HISTORY VERIFIED',len(verified),'artifacts;',len(m['frozen_source_sha256']),'sources; D1/D2 exact imports 40+40; zero rerun')
if __name__=='__main__':run()
