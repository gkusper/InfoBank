"""Gold-blind runtime projection; original annotation extraction is a separate writer."""
import hashlib,json,re,collections,platform,datetime
from .artifacts import *
from evaluation.cfaf_target_claim_alignment_v1 import integration as impl
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,catalogue_payload
INPUT_BUDGET=60000
CONTEXT_POLICY='Original-order whole-passage prefix, maximal within 60000 UTF-8 serialized-byte upper bound on input tokens; no content/label ranking.'
RUNTIME_KEYS={'question','question_date','grounding'}
GOLD_KEYS={'answer_generate','answer_related_info','answer_validate','evidence_relevant','evidence_correct','evidence_cited','comments','question_valid','question_false_premise','question_seeking','question_sensitive','question_type','question_complexity','question_category','question_popularity','question_tag','topic_tag'}
def byte_upper_bound(value):return len(json.dumps(value,ensure_ascii=True,sort_keys=True).encode('utf-8'))+128

def passage(p,index):
 markers=[k for k in p if re.fullmatch(r'cite_\d+',k)]
 if len(markers)!=1 or not isinstance(p[markers[0]],str) or not p[markers[0]].strip():raise ValueError('INVALID_GROUNDING_PASSAGE')
 if markers[0]!=f'cite_{index+1}':raise ValueError('NONSEQUENTIAL_ORIGINAL_CITATION')
 allowed={'age','date','provider',markers[0]}
 if set(p)-allowed:raise ValueError('UNEXPECTED_GROUNDING_METADATA')
 metadata={k:p[k] for k in ['age','date','provider'] if k in p}
 header=json.dumps({'citation_marker':markers[0],**metadata},ensure_ascii=False,sort_keys=True)+'\n'
 return markers[0],header+p[markers[0]],metadata,len(header)

def runtime_projection(public):
 if set(public)!=RUNTIME_KEYS:raise ValueError('EXACT_RUNTIME_WHITELIST_REQUIRED')
 if not isinstance(public['question'],str) or not public['question'].strip():raise ValueError('EMPTY_QUERY')
 sources=[];mapping=[];bounds=[]
 case={'case_id':'private-runtime-case','pair_id':'unpaired','family':'supplied-grounding','variant':'none','query':public['question'],'sources':sources}
 query_context={'question_date':public['question_date'],'date_interpretation':'Use the supplied question date as the as-of date; source dates/ages are original supplied metadata.'}
 for index,p in enumerate(public['grounding']):
  marker,context,metadata,header_length=passage(p,index)
  source={'source_id':f'private-garage-source-{index+1:04d}','title':f'private-garage-source-title-{index+1:04d}','source_type':'Document','content':context,'metadata':{},'retrieved':True,'access_mode':'FULL','existence_visibility':'PUBLIC','purpose_compatibility':'compatible','security_status':'clean'}
  sources.append(source);request=impl.project_case(case);docs={d['source_id']:d['context'] for d in request.documents}
  payload={**request.public(),'query_context':query_context,'span_catalogue':catalogue_payload(docs,build_catalogue(docs))}
  schema=impl.ANALYSIS_SCHEMA
  envelope={'model':'gpt-4o-mini','messages':[{'role':'system','content':impl.GOVERNED_PROMPT},{'role':'user','content':json.dumps(payload,ensure_ascii=True,sort_keys=True)}],'response_format':{'type':'json_schema','json_schema':{'name':'structured_response','strict':True,'schema':schema}}}
  bound=byte_upper_bound(envelope)
  if bound>INPUT_BUDGET:sources.pop();break
  bounds.append(bound);mapping.append({'original_index_zero_based':index,'original_marker':marker,'source_id':f'view-{index+1:04d}','raw_text_sha256':hashlib.sha256(p[marker].encode('utf-8')).hexdigest(),'adapted_context_sha256':hashlib.sha256(context.encode('utf-8')).hexdigest(),'metadata_header_characters':header_length,'source_metadata':metadata})
 if not sources:raise ValueError('FIRST_PASSAGE_EXCEEDS_DECLARED_INPUT_BUDGET')
 return {'case':case,'query_context':query_context,'mapping':mapping,'original_grounding_count':len(public['grounding']),'included_count':len(sources),'omitted_original_markers':[f'cite_{i+1}' for i in range(len(sources),len(public['grounding']))],'altered_context':len(sources)!=len(public['grounding']),'analysis_input_token_upper_bound':bounds[-1]}

def prepare():
 if (ROOT/'runtime_inputs.jsonl').exists():raise RuntimeError('Inputs already prepared; do not overwrite frozen sample')
 original=rows(ROOT/'datasets/GaRAGe_benchmark.jsonl');selected=rows(ROOT/'selected_records.jsonl');selection=read(ROOT/'dataset3_selection_manifest.json');audit=read(ROOT/'local/source_audit.json')
 ids=[r['sample_id'] for r in original];counts=[len(r['grounding']) for r in original]
 audit.update(unique_ids=len(set(ids)),missing_ids=sum(not x for x in ids),duplicate_ids=len(ids)-len(set(ids)),grounding_total=sum(counts),grounding_count_distribution=dict(collections.Counter(counts)),grounding_min=min(counts),grounding_max=max(counts),grounding_mean=sum(counts)/len(counts),annotation_values={k:dict(collections.Counter(v for r in original for v in (r[k] if isinstance(r[k],list) else [r[k]]))) for k in ['evidence_relevant','evidence_correct','evidence_cited','question_valid','question_false_premise','question_seeking','question_sensitive','question_type','question_complexity','question_category','question_popularity','answer_validate']},annotation_alignment_errors=sum(any(len(r[k])!=len(r['grounding']) for k in ['evidence_relevant','evidence_correct','evidence_cited']) for r in original))
 write(ROOT/'source_audit.json',audit)
 for i,r in enumerate(selected):
  runtime=runtime_projection({k:r[k] for k in RUNTIME_KEYS});runtime['runtime_index']=i;append(ROOT/'runtime_inputs.jsonl',runtime)
  append(ROOT/'gold_annotations.jsonl',{'runtime_index':i,'sample_id':r['sample_id'],**{k:r[k] for k in GOLD_KEYS}})
  selection['records'][i].update(sample_id=r['sample_id'],question_date=r['question_date'],category=r['question_category'],complexity=r['question_complexity'],grounding_count=len(r['grounding']),included_count=runtime['included_count'],altered_context=runtime['altered_context'])
 write(ROOT/'dataset3_selection_manifest.json',selection)
 write(ROOT/'dataset3_exposure_ledger.json',{'dataset':'Dataset3 original AmazonScience GaRAGe','source_commit':audit['commit'],'seed':20261028,'selected_sample_ids':[r['sample_id'] for r in selected],'exposed':10,'remaining_not_qualitatively_inspected':len(original)-10,'development_pilot':True,'independent_final_assessment':False,'other_dataset_ledgers_modified':False})
 print(json.dumps({'rows':len(original),'groundings':sum(counts),'ids_unique':audit['unique_ids'],'annotation_values':audit['annotation_values'],'selected':selection['records']},indent=2))
if __name__=='__main__':prepare()
