"""Run original regressions against pristine base and extended source in isolated copies.

Git cat-file preserves exact repository blob bytes and mixed line endings,
avoiding Windows checkout conversion artifacts. No frozen files in the working checkout are changed or removed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
BASE='5f377de38312fb39c088551f9c74f8b6d4bd5080'


def report_details(path):
    tree=ET.parse(path).getroot();suites=[tree] if tree.tag=='testsuite' else list(tree)
    failures=[]
    for testcase in tree.iter('testcase'):
        for item in list(testcase):
            if item.tag in {'failure','error'}:
                failures.append({'test':testcase.attrib.get('classname','')+'::'+testcase.attrib['name'],'type':item.tag,'message':item.attrib.get('message','')})
    return {'tests':sum(int(s.attrib.get('tests',0)) for s in suites),
        'failures':failures,'failure_count':len(failures),'passed':sum(int(s.attrib.get('tests',0))-int(s.attrib.get('failures',0))-int(s.attrib.get('errors',0))-int(s.attrib.get('skipped',0)) for s in suites)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args();work=args.work_dir.resolve();work.mkdir(parents=True,exist_ok=True)
    # cat-file --batch returns exact blob bytes, preserving the repository's
    # deliberate mix of LF and CRLF rather than Windows checkout conversion.
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=REPO,text=True).splitlines()
    blob_output=subprocess.check_output(['git','cat-file','--batch'],cwd=REPO,
        input=''.join(BASE+':'+name+'\n' for name in names).encode())
    blobs={};position=0
    for name in names:
        header_end=blob_output.index(b'\n',position)
        header=blob_output[position:header_end].split();size=int(header[-1])
        assert header[1]==b'blob'
        position=header_end+1;blobs[name]=blob_output[position:position+size];position+=size+1
    summaries={}
    for variant in ['baseline','extended']:
        dest=work/variant
        if dest.exists():raise RuntimeError('Isolated regression directory exists; use a fresh path.')
        dest.mkdir()
        for name,payload in blobs.items():
            target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
        shutil.copytree(REPO/'.git',dest/'.git')
        if variant=='extended':
            shutil.copy2(REPO/'evaluation/wolala2026/semantic_evidence.py',dest/'evaluation/wolala2026/semantic_evidence.py')
        paths=sorted(str(p.relative_to(dest)) for p in (dest/'evaluation/tests').glob('test_wolala*.py'))
        xml=HERE/('baseline_regression_tests.xml' if variant=='baseline' else 'regression_tests.xml')
        env=dict(os.environ);env.pop('OPENAI_API_KEY',None)
        command=[sys.executable,'-m','pytest',*paths,'-q','-p','no:cacheprovider','--basetemp',str(work/(variant+'-tmp')),'--junitxml',str(xml)]
        status=subprocess.call(command,cwd=dest,env=env)
        summaries[variant]={'exit_code':status,**report_details(xml)}
    same=summaries['baseline']['failures']==summaries['extended']['failures']
    payload={'base_commit':BASE,'exact_repository_blob_bytes_used':True,'runs':summaries,
        'no_new_regression_failures':same,'all_original_regressions_pass':not summaries['extended']['failures'],
        'acceptance_condition_5_fully_satisfied':not summaries['extended']['failures'],
        'preexisting_failure_explanation':'The committed preheldout_v3_attempt1 authorization artifact conflicts with an old plan-only test asserting its absence. No frozen artifact is removed to make this pass.',
        'exploratory_run_policy':'Proceed only if synthetic acceptance passes and exact baseline failure set is unchanged. Report the pre-existing failure explicitly; do not claim all original tests passed.'}
    (HERE/'regression_comparison.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in payload.items() if k!='runs'},indent=2))
    if not same:sys.exit(1)


if __name__=='__main__':main()
