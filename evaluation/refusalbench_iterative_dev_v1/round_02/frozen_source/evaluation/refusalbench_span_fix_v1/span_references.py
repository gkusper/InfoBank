"""Deterministic reference catalogues; no model-generated source quotations."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import copy,hashlib,json
from evaluation.wolala2026.semantic_evidence import (ANALYSIS_PROMPT as OLD_PROMPT,
 ASSESSMENT_SCHEMA,_schema_errors,parse_assessment,unknown_assessment)

WINDOW=430;OVERLAP=70
REFERENCE_SCHEMA=copy.deepcopy(ASSESSMENT_SCHEMA)
for name in ['supporting_spans','contradicting_spans']:
 REFERENCE_SCHEMA['properties'][name]={'type':'array','items':{'type':'string'}}
OLD_QUOTE='Quote minimal exact supporting and contradicting passages with their supplied source_id. Copy quotes exactly, including punctuation; do not invent passages.'
NEW_QUOTE='Identify supporting and contradicting evidence using only span_id strings from the deterministic span_catalogue. Never generate quotation text, offsets, or invented IDs. A span may be both supporting and contradicting if it contains both claims. Preserve every identified counterevidence reference; a valid ID is not proof of sufficient support.'
assert OLD_QUOTE in OLD_PROMPT
ANALYSIS_PROMPT=OLD_PROMPT.replace(OLD_QUOTE,NEW_QUOTE)


def text_hash(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class Span:
 source_id:str
 span_id:str
 start_offset:int
 end_offset:int
 source_sha256:str

@dataclass
class Catalogue:
 spans:dict[str,Span]
 source_hashes:dict[str,str]
 window:int=WINDOW
 overlap:int=OVERLAP


def build_catalogue(documents,window=WINDOW,overlap=OVERLAP):
 if type(window) is not int or type(overlap) is not int or window<1 or not 0<=overlap<window:
  raise ValueError('Invalid deterministic window/overlap.')
 spans={};hashes={}
 for source_id,text in sorted(documents.items()):
  if not isinstance(source_id,str) or not isinstance(text,str):raise ValueError('Sources and context must be strings.')
  hashes[source_id]=text_hash(text)
  for index,start in enumerate(range(0,len(text),window-overlap)):
   end=min(start+window,len(text));sid=f'{source_id}:span-{index:04d}'
   spans[sid]=Span(source_id,sid,start,end,hashes[source_id])
   if end==len(text):break
 return Catalogue(spans,hashes,window,overlap)


def resolve_span(reference,documents,catalogue):
 if not isinstance(reference,str) or reference not in catalogue.spans:raise ValueError('UNKNOWN_SPAN_ID:'+str(reference))
 span=catalogue.spans[reference]
 if span.source_id not in documents:raise ValueError('UNKNOWN_SOURCE_ID')
 text=documents[span.source_id]
 if text_hash(text)!=catalogue.source_hashes.get(span.source_id) or span.source_sha256!=text_hash(text):raise ValueError('SOURCE_CONTENT_CHANGED')
 if type(span.start_offset) is not int or type(span.end_offset) is not int or not 0<=span.start_offset<span.end_offset<=len(text):raise ValueError('INVALID_OFFSETS')
 expected=build_catalogue(documents,catalogue.window,catalogue.overlap).spans.get(reference)
 if span!=expected or span.span_id!=reference:raise ValueError('CATALOGUE_MISMATCH')
 return {'source_id':span.source_id,'span_id':span.span_id,'quote':text[span.start_offset:span.end_offset],
  'start':span.start_offset,'end':span.end_offset}


def catalogue_payload(documents,catalogue):
 return [{**asdict(span),'text':resolve_span(sid,documents,catalogue)['quote']} for sid,span in catalogue.spans.items()]


def parse_reference_assessment(raw,documents,catalogue,model='unknown'):
 audit={'valid':False,'reference_valid':None,'validated_reference_count':0,'reference_errors':[],'errors':[],'supporting_references':[],'contradicting_references':[],'resolved_spans':[]}
 try:data=json.loads(raw)
 except (ValueError,TypeError):return unknown_assessment(['INVALID_JSON'],model),audit
 errors=_schema_errors(data,REFERENCE_SCHEMA)
 if errors:
  audit['errors']=errors;return unknown_assessment(errors,model),audit
 converted=copy.deepcopy(data);resolved={}
 for field in ['supporting_spans','contradicting_spans']:
  audit['supporting_references' if field=='supporting_spans' else 'contradicting_references']=list(data[field])
  converted[field]=[]
  for reference in data[field]:
   try:span=resolve_span(reference,documents,catalogue)
   except ValueError as exc:errors.append(str(exc));audit['reference_errors'].append(str(exc));continue
   audit['validated_reference_count']+=1
   resolved[field,reference]=span
   converted[field].append({'source_id':span['source_id'],'quote':span['quote']})
 if errors:
  audit['reference_valid']=False;audit['errors']=errors;return unknown_assessment(errors,model),audit
 audit['reference_valid']=True
 audit['resolved_spans']=list({span['span_id']:span for span in resolved.values()}.values())
 assessment=parse_assessment(json.dumps(converted),documents,model)
 if assessment.valid:
  for field in ['supporting_spans','contradicting_spans']:
   assessment.data[field]=[resolved[field,reference] for reference in data[field]]
  audit['resolved_spans']=list({span['span_id']:span for span in resolved.values()}.values())
 audit['valid']=assessment.valid;audit['errors']=assessment.validation_errors
 return assessment,audit


def analyze_evidence(query,documents,provider):
 catalogue=build_catalogue(documents)
 payload={'query':query,'documents':[{'source_id':k,'context':v} for k,v in documents.items()],
  'span_catalogue':catalogue_payload(documents,catalogue)}
 call=provider.generate_json(mode_name='semantic_analysis',system_prompt=ANALYSIS_PROMPT,user_payload=payload,max_output_tokens=1500)
 assessment,audit=parse_reference_assessment(call.content,documents,catalogue,call.model)
 call.reference_audit=audit;call.span_catalogue=catalogue_payload(documents,catalogue)
 return assessment,call
