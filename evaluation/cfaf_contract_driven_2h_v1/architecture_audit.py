"""Reuse inventory without importing side-effectful backend services."""
import ast,importlib.metadata as md,sqlite3,sys,json
from .artifacts import *
def run():
 current=['backend_python/ai_service.py','backend_python/document_processing.py','backend_python/routing.py','backend_python/policy_engine.py','backend_python/aggregate_executor.py','backend_python/evidence_service.py','backend_python/controlled_failure.py','backend_python/citation_service.py'];files=[]
 for name in current:
  p=REPO/name
  if p.exists():
   tree=ast.parse(p.read_text(encoding='utf-8-sig'));files.append({'path':name,'available':True,'sha256':sha(p),'functions':[{'name':n.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))],'license':'Repository CC-BY-NC-4.0'})
  else:files.append({'path':name,'available':False,'action':'Do not invent module; use actual current evaluation implementation'})
 reference=REPO.parents[1]/'work/target-claim-remote-main'
 for name in ['backend_python/aggregate_executor.py','backend_python/citation_service.py']:
  p=reference/name
  if p.exists():files.append({'path':str(p),'available':True,'reference_only':True,'source_commit':'8079f29dc3a97273f51b55b2a22f9ff896a2e758','sha256':sha(p),'license':'Not independently verified in partial cached main source; not adopted into measured pipeline'})
 dependencies=[]
 for name in ['chromadb','PyMuPDF','pydantic','SQLAlchemy','spacy','networkx','sentence-transformers','casbin','duckdb','haystack-ai','pyarrow','datasets','numpy','pytest']:
  try:
   dist=md.distribution(name);dependencies.append({'name':name,'installed':True,'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License'),'recommendation':'Use only existing benchmark IO/statistics dependencies; no replacements added'})
  except md.PackageNotFoundError:dependencies.append({'name':name,'installed':False,'license':'Not verified for proposed replacement; no dependency recommended/installed'})
 conn=sqlite3.connect(':memory:');conn.execute('CREATE VIRTUAL TABLE evidence USING fts5(content)')
 write(ROOT/'component_inventory.json',{'python':sys.version,'stdlib_license':'PSF License Version 2; retained standard runtime','sqlite_version':sqlite3.sqlite_version,'FTS5_available':True,'sqlite_license':'Public domain; no retrieval replacement executed','repository_license_sha256':sha(REPO/'LICENSE'),'modules':files,'dependencies':dependencies,'architecture_replacements_executed':False,'one_call_ablation':'PROPOSED_ONLY','backend_imports_executed':False,'new_packages_installed':[]})
 print('Reuse audit saved:',len(files),'module entries;',sum(d['installed'] for d in dependencies),'installed candidate/dependency packages')
if __name__=='__main__':run()
