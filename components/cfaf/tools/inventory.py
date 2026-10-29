"""Source, dependency and code-size inventory without importing legacy runtime."""
from common import *
import ast,importlib.metadata as meta,importlib.util,sqlite3,sys

def size(path):
    text=path.read_text(encoding='utf-8-sig');tree=ast.parse(text);doclines=set()
    for node in ast.walk(tree):
        if isinstance(node,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):doclines.update(range(node.body[0].lineno,node.body[0].end_lineno+1))
    code=sum(bool(line.strip()) and not line.lstrip().startswith('#') and i not in doclines for i,line in enumerate(text.splitlines(),1))
    statements=sum(isinstance(n,ast.stmt) and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)) for n in ast.walk(tree))
    return {'physical_lines':len(text.splitlines()),'nonblank_noncomment_nondocstring_lines':code,'AST_statements':statements,'bytes':len(path.read_bytes())}

def closure(roots):
    seen=set();todo=list(roots)
    while todo:
        path=todo.pop()
        if path in seen or not path.is_file():continue
        seen.add(path);module='.'.join(path.relative_to(REPO).with_suffix('').parts);package=module.rsplit('.',1)[0]
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[]
            if isinstance(node,ast.Import):names=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                try:base=importlib.util.resolve_name('.'*node.level+(node.module or ''),package) if node.level else node.module or ''
                except (ImportError,ValueError):continue
                names=[base]+[base+'.'+a.name for a in node.names if a.name!='*']
            for name in names:
                candidate=REPO/Path(*name.split('.'))
                for dep in [candidate.with_suffix('.py'),candidate/'__init__.py']:
                    if dep.is_file():todo.append(dep)
    return sorted(seen)

def main():
    ensure();verify_freeze();state=read(STATE);runtime=sorted((ROOT/'src/component_cfaf').rglob('*.py'));copied={'adapters/legacy_projection.py','adapters/aggregate_core.py'};metrics={p.relative_to(ROOT).as_posix():size(p) for p in runtime};new=[p for p in runtime if p.relative_to(ROOT/'src/component_cfaf').as_posix() not in copied];old=[p for p in runtime if p not in new];adapters=[p for p in runtime if p.parent.name=='adapters']
    def total(paths):return {k:sum(size(p)[k] for p in paths) for k in ['physical_lines','nonblank_noncomment_nondocstring_lines','AST_statements','bytes']}
    baseline=closure([REPO/'evaluation/cfaf_contract_driven_2h_v1'/name for name in ['measured_c.py','provider.py','systems.py']]);docs=list(ROOT.glob('*.md'))
    report={'counting_method':'Physical lines; nonblank/noncomment lines excluding AST docstrings; AST statement count also reported to expose semicolon/compact formatting. Adapters are a subset, not an extra additive group. Third-party library source is excluded from both own-code counts.','new_own_runtime':total(new),'copied_own_runtime':total(old),'all_runtime_including_copies':total(runtime),'adapter_subset_including_copies':total(adapters),'tests':total(list((ROOT/'tests').glob('*.py'))),'experiment_tools':total(list((ROOT/'tools').glob('*.py'))),'documentation_physical_lines':sum(len(p.read_text(encoding='utf-8-sig').splitlines()) for p in docs),'historical_static_local_import_closure':{'roots':['measured_c.py','provider.py','systems.py'],'files':len(baseline),'size':total(baseline),'paths':[p.relative_to(REPO).as_posix() for p in baseline],'caveat':'Static local imports, including conditional imports; not a measured runtime call graph. The new configuration has narrower integrations and different semantics, so this is not equivalent-functionality reduction.'},'per_runtime_file':metrics}
    write(ROOT/'code_size_report.json',report)
    dependencies=[]
    for d in sorted(meta.distributions(),key=lambda d:d.metadata['Name'].lower()):
        if d.metadata['Name'].lower()=='component-cfaf':continue
        dependencies.append({'name':d.metadata['Name'],'version':d.version,'license_expression':d.metadata.get('License-Expression'),'license_metadata':(d.metadata.get('License') or '')[:180],'license_classifiers':[x for x in d.metadata.get_all('Classifier',[]) if x.startswith('License ::')]})
    reused=[]
    for name,original in [('legacy_projection.py','evaluation/infobank_semantic_regression_v1/policy_projection.py'),('aggregate_core.py','evaluation/cfaf_target_claim_alignment_v1/vendor/aggregate_core.py')]:
        copied_path=ROOT/'src/component_cfaf/adapters'/name;blob=subprocess.check_output(['git','show',state['base']+':'+original],cwd=REPO);assert copied_path.read_bytes().replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n');reused.append({'file':copied_path.relative_to(ROOT).as_posix(),'source_path':original,'base_commit':state['base'],'working_copy_sha256':sha(copied_path),'original_git_blob_sha256':hashlib.sha256(blob).hexdigest(),'difference_if_any':'Git checkout newline representation only'})
    write(ROOT/'component_manifest.json',{'package':'component-cfaf','version':'0.1.0','branch':'ComponentBasaedCFAF','base_commit':state['base'],'repository_license':'CC-BY-NC-4.0','license_sha256':sha(REPO/'LICENSE'),'python':sys.version,'SQLite':sqlite3.sqlite_version,'SQLite_fts5_available':True,'dependency_distributions':dependencies,'reused_runtime':reused,'selector_origin':{'path':'evaluation/wolala2026/pipeline.py','base':state['base'],'differential_states':300},'core_imports_versioned_experiment_or_dataset_scorer':False,'optional_components':{x:'NOT_IMPLEMENTED_OPTIONAL' for x in ['spaCy','NLI','Chroma/FastEmbed','Casbin','DuckDB','Haystack','LangChain','LangGraph','LlamaIndex']},'dataset_registry':{'Dataset1':'InfoBank exposed development','Dataset2':'RefusalBench-NQ exposed development; protected 30+18 groups untouched','Dataset3-v1':'GaRAGe historical grounding','Dataset3-QASPER-v2-candidate':'Historical registry key; separate completed replacement study untouched; no QASPER inputs used here'},'model_revision':read(ROOT/'api_usage.json')['models_observed'],'runtime_downloads':False,'package_installation_environment':'Dedicated component-cfaf-v1/venv; independent legacy-venv for pyarrow-only historical tests','frozen_manifest_sha256':sha(ROOT/'results/freeze.json')})
    ablation=read(ROOT/'results/renderer_ablation.json')
    if 'cases' in ablation:write(ROOT/'results/local/renderer_ablation_cases.json',ablation.pop('cases'));write(ROOT/'results/renderer_ablation.json',ablation)
    print(json.dumps({'new_runtime':report['new_own_runtime'],'copied_runtime':report['copied_own_runtime'],'baseline':report['historical_static_local_import_closure']['size'],'baseline_files':len(baseline)},indent=2))
if __name__=='__main__':main()
