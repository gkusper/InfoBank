"""Check preflight artifacts; optionally initialize only a NEW experiment manifest."""
import argparse,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from .prepare_dataset import ROOT,REPO,sha,dump
from .execute import freeze_hashes


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--initialize',action='store_true',help='Write audit/manifest only if neither already exists.');args=parser.parse_args()
 protected=json.loads((ROOT/'protected_files.json').read_text());changed=[n for n,h in protected.items() if sha(REPO/n)!=h]
 if changed:raise RuntimeError('Previously frozen files changed: '+','.join(changed))
 counts={}
 for name in ['test_results.xml','historical_regressions.xml']:
  tests=list(ET.parse(ROOT/name).getroot().iter('testcase'));failed=[t.get('name') for t in tests if t.find('failure') is not None or t.find('error') is not None];counts[name]={'testcases':len(tests),'failures':failed}
  permitted=['test_preheldout_attempt1_plan_artifacts_are_plan_only'] if name=='historical_regressions.xml' else []
  if failed!=permitted:raise RuntimeError('Unexpected preflight failure: '+name+':'+repr(failed))
 filtering=json.loads((ROOT/'filtering_report.json').read_text());source=Path(filtering['original_file'])
 if sha(source)!=filtering['original_file_sha256']:raise RuntimeError('Official dataset checksum changed.')
 if args.initialize:
  if (ROOT/'experiment_manifest.json').exists() or (ROOT/'regression_audit.json').exists():raise RuntimeError('Initialization refuses to overwrite an existing experiment.')
  audit={'status':'PASS_WITH_KNOWN_HISTORICAL_FAILURE','tests':counts,'historical_known_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only','prior_files_protected':len(protected),'prior_files_changed':changed,'official_dataset_sha256':sha(source),'api_calls':0}
  manifest={'version':'refusalbench-noncontradiction-v1','branch':subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),'parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'implementation':'semantic-integration-v2.1 unchanged','code_sha256':freeze_hashes(),'preparation_sha256':{n:sha(ROOT/n) for n in ['selected_cases.jsonl','filtered_selection_manifest.json','filtering_report.json']},'preparation_code_sha256':sha(ROOT/'prepare_dataset.py'),'dataset_revision':filtering['revision'],'original_dataset_sha256':sha(source),'seed':20261028,'model':'gpt-4o-mini','temperature':0,'analysis_max_tokens':1500,'generation_max_tokens':160,'hard_api_attempt_cap':75,'planned_api_calls':60,'repetitions':1,'status':'PREFLIGHT_COMPLETE'}
  dump(ROOT/'regression_audit.json',audit);dump(ROOT/'experiment_manifest.json',manifest)
 print(json.dumps({'preflight':'PASS_WITH_KNOWN_HISTORICAL_FAILURE','tests':counts,'previous_files_unchanged':len(protected),'official_dataset_unchanged':True,'initialized':args.initialize}))
if __name__=='__main__':main()
