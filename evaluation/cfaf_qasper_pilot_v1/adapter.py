"""Gold-blind QASPER paper adapter with deterministic SQLite FTS5/BM25 fallback."""
import re,sqlite3,hashlib,json
from .artifacts import *
from . import measured_c as impl
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,catalogue_payload
from evaluation.cfaf_dataset3_garage_pilot_v1.adapter import byte_upper_bound
INPUT_BUDGET=110000
RUNTIME_FIELDS={'question','title','abstract','full_text','figures_and_tables'}
def paragraphs(public):
 if set(public)!=RUNTIME_FIELDS:raise ValueError('EXACT_QASPER_RUNTIME_WHITELIST_REQUIRED')
 ps=[]
 for si,s in enumerate(public['full_text']):
  for pi,text in enumerate(s['paragraphs']):
   if text.strip():ps.append({'key':f'P{len(ps):04d}','kind':'paragraph','section':s['section_name'],'text':text,'section_index':si,'paragraph_index':pi})
 for fi,f in enumerate(public['figures_and_tables']):
  if f.get('caption','').strip():ps.append({'key':f'P{len(ps):04d}','kind':'caption','section':'Figure/table caption','text':f['caption'],'figure_index':fi})
 return ps

def render(public,ps):
 out='TITLE\n'+public['title']+'\nABSTRACT\n'+public['abstract']+'\n';mapping=[]
 for p in sorted(ps,key=lambda p:p['key']):
  out+='\n['+p['key']+'] '+p['section']+'\n';start=len(out);out+=p['text']+'\n';mapping.append({**p,'start':start,'end':start+len(p['text'])})
 return out,mapping

def make_case(question,context):
 return {'case_id':'private-qasper-runtime','pair_id':'unpaired','family':'public-document-qa','variant':'neutral','query':question,'sources':[{'source_id':'private-qasper-document','title':'private-qasper-catalogue-title','source_type':'Document','content':context,'metadata':{},'retrieved':True,'access_mode':'FULL','existence_visibility':'PUBLIC','purpose_compatibility':'compatible','security_status':'clean'}]}

def bound(case):
 request=impl.project_case(case);docs={d['source_id']:d['context'] for d in request.documents};payload={**request.public(),'span_catalogue':catalogue_payload(docs,build_catalogue(docs)),'query_context':{}}
 env={'model':'gpt-4o-mini','messages':[{'role':'system','content':impl.GOVERNED_PROMPT},{'role':'user','content':json.dumps(payload,ensure_ascii=True,sort_keys=True)}],'temperature':0,'max_tokens':1500,'response_format':{'type':'json_schema','json_schema':{'name':'structured_response','strict':True,'schema':impl.ANALYSIS_SCHEMA}}}
 return byte_upper_bound(env)

def rank(ps,query):
 db=sqlite3.connect(':memory:');db.execute('CREATE VIRTUAL TABLE passages USING fts5(content, tokenize="unicode61")');db.executemany('INSERT INTO passages(rowid,content) VALUES (?,?)',[(i+1,p['text']) for i,p in enumerate(ps)])
 terms=list(dict.fromkeys(re.findall(r'\w{2,}',query,flags=re.UNICODE)))
 expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
 hits=[i-1 for i,score in db.execute('SELECT rowid,bm25(passages) FROM passages WHERE passages MATCH ? ORDER BY bm25(passages),rowid',(expression,))] if expression else []
 db.close();return hits+[i for i in range(len(ps)) if i not in set(hits)]

def project(public):
 ps=paragraphs(public);context,mapping=render(public,ps);case=make_case(public['question'],context);whole_bound=bound(case)
 if whole_bound<=INPUT_BUDGET:chosen=ps;method='WHOLE_PAPER'
 else:
  chosen=[];method='SQLITE_FTS5_BM25';assert bound(make_case(public['question'],render(public,[])[0]))<=INPUT_BUDGET
  for i in rank(ps,public['question']):
   candidate=chosen+[ps[i]];text,_=render(public,candidate)
   if bound(make_case(public['question'],text))<=INPUT_BUDGET:chosen=candidate
  context,mapping=render(public,chosen);case=make_case(public['question'],context)
 return {'case':case,'query_context':{},'mapping':[],'paragraph_mapping':mapping,'retrieval_method':method,'available_paragraphs':len(ps),'included_paragraphs':len(chosen),'omitted_paragraph_keys':[p['key'] for p in ps if p not in chosen],'altered_context':len(ps)!=len(chosen),'analysis_input_token_upper_bound':bound(case),'full_paper_bound':whole_bound,'context_sha256':hashlib.sha256(context.encode()).hexdigest(),'trusted_fixture_ingestion':False}

def prepare():
 ensure();assert not (ROOT/'local/runtime_inputs.jsonl').exists()
 for s in rows(ROOT/'local/selected_originals.jsonl'):
  p=s['paper'];public={'question':s['question']['question'],**{k:p[k] for k in RUNTIME_FIELDS if k!='question'}};runtime=project(public);runtime['runtime_index']=s['runtime_index'];append(ROOT/'local/runtime_inputs.jsonl',runtime)
  safe={k:v for k,v in runtime.items() if k not in {'case','paragraph_mapping','mapping','query_context'}};safe['question_sha256']=hashlib.sha256(public['question'].encode()).hexdigest();safe['runtime_record_sha256']=hashlib.sha256(canonical(runtime).encode()).hexdigest();append(ROOT/'RUNTIME_INPUTS.jsonl',safe)
 write(ROOT/'local/runtime_manifest.json',{'runtime_sha256':sha(ROOT/'local/runtime_inputs.jsonl'),'public_runtime_sha256':sha(ROOT/'RUNTIME_INPUTS.jsonl'),'count':10})
 print('PREPARED',[(r['runtime_index'],r['retrieval_method'],r['included_paragraphs'],r['available_paragraphs'],r['analysis_input_token_upper_bound']) for r in rows(ROOT/'RUNTIME_INPUTS.jsonl')])
if __name__=='__main__':prepare()
