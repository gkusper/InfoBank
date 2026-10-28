"""Candidate fragments are proposals; exact offsets are not semantic entailment."""
import json,re
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span
WORDS={'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90,'dozen':12}
NUMBER=r'(?:\d+(?:[,.]\d+)*|'+ '|'.join(WORDS)+r')'
NUM_RE=re.compile(r'(?<!\w)'+NUMBER+r'(?!\w)',re.I)
DATE_RE=re.compile(r'\b(?:\d{4}s?|(?:January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+\d{1,2})?(?:,?\s+\d{4})?)\b',re.I)

def _fragment(text,start,end,origin):return {'text':text[start:end],'start':start,'end':end,'provenance':origin}
def _unit(req):
 m=re.search(r'\bhow many\s+([\w-]+)',req['request_text'],re.I)
 return m.group(1) if m else None

def _numeric(text,req):
 unit=_unit(req)
 if unit:
  matches=list(re.finditer(r'(?<!\w)('+NUMBER+r')\s+'+re.escape(unit)+r'\b',text,re.I))
  if matches:return [_fragment(text,m.start(1),m.end(1),'DETERMINISTIC_NUMERIC_TOKEN_SHAPE') for m in matches]
 return [_fragment(text,m.start(),m.end(),'DETERMINISTIC_NUMERIC_TOKEN_SHAPE') for m in NUM_RE.finditer(text)]

def propose_fragments(candidate,requirement,data,multipart=False):
 if not isinstance(candidate,str) or not candidate.strip():return []
 kind=requirement['answer_type']
 if kind in {'COUNT','QUANTITY','DURATION'}:return _numeric(candidate,requirement)
 if kind=='DATE_TIME':return [_fragment(candidate,m.start(),m.end(),'DETERMINISTIC_TEMPORAL_TOKEN_SHAPE') for m in DATE_RE.finditer(candidate)]
 if kind=='NAMED_IDENTITY':
  proposals=[]
  for entity in data.get('entities',[]):
   if isinstance(entity,str) and entity.strip():
    proposals.extend(_fragment(candidate,m.start(),m.end(),'LLM_ENTITY_PROPOSAL_WITH_EXACT_OFFSETS') for m in re.finditer(re.escape(entity),candidate,re.I))
  unique={(r['start'],r['end']):r for r in proposals};result=sorted(unique.values(),key=lambda r:(r['start'],-r['end']))
  # Suppress an entity substring when an explicitly proposed longer entity spans it.
  return [r for r in result if not any(o['start']<=r['start'] and o['end']>=r['end'] and o!=r for o in result)]
 if kind=='BOOLEAN':return [_fragment(candidate,m.start(),m.end(),'DETERMINISTIC_BOOLEAN_TOKEN_SHAPE') for m in re.finditer(r'\b(?:yes|no|true|false)\b',candidate,re.I)]
 if kind=='LOCATION':
  entities=[_fragment(candidate,m.start(),m.end(),'LLM_ENTITY_PROPOSAL_LOCATION_UNVERIFIED') for e in data.get('entities',[]) if isinstance(e,str) and e for m in re.finditer(re.escape(e),candidate,re.I)]
  if entities:return entities
 if not multipart:return [_fragment(candidate,0,len(candidate),'WHOLE_CANDIDATE_TYPE_UNVERIFIED')]
 # Attribute fragments are conservatively proposed; no arbitrary prose entails them.
 operation=requirement['relation_or_operation']
 if operation.startswith('ATTRIBUTE:'):
  attr=operation.split(':',1)[1];m=re.search(re.escape(attr)+r'\s+(?:is|was|:)\s*([^,;.]+)',candidate,re.I)
  if m:return [_fragment(candidate,m.start(1),m.end(1),'ATTRIBUTE_PATTERN_PROPOSAL')]
 return [_fragment(candidate,0,len(candidate),'COMPOSITE_CANDIDATE_NOT_ISOLATED')]

def _compatible(fragment,req,native=False):
 if fragment is None:return None
 value=fragment['text'];kind=req['answer_type']
 if native:
  if kind in {'COUNT','QUANTITY','DURATION'}:return type(value) in {int,float} and (kind!='COUNT' or type(value) is int)
  if kind=='BOOLEAN':return type(value) is bool
  return isinstance(value,str) and bool(value.strip())
 if kind in {'COUNT','QUANTITY','DURATION'}:return bool(NUM_RE.fullmatch(value))
 if kind=='DATE_TIME':return bool(DATE_RE.fullmatch(value))
 if kind=='BOOLEAN':return value.casefold() in {'yes','no','true','false'}
 if kind=='NAMED_IDENTITY':return None if NUM_RE.fullmatch(value) or not any(c.isalpha() for c in value) else True
 return None # semantic type/location/definition cannot be proved by arbitrary text shape

def _norm(value):
 v=value.casefold();return WORDS.get(v,v.replace(',',''))

def association(req,fragment,parent_fragments,evidence):
 if not req['depends_on']:return {'status':'NOT_APPLICABLE','semantic_support':'NOT_APPLICABLE'}
 if not fragment or not parent_fragments:return {'status':'UNRESOLVED_ANTECEDENT','semantic_support':'UNKNOWN'}
 if len(parent_fragments)!=1:return {'status':'MULTIPLE_CANDIDATE_REFERENTS','semantic_support':'UNKNOWN'}
 name=parent_fragments[0]['text'];wanted=_norm(str(fragment['text']));observed=[]
 for source in evidence:
  for clause in re.split(r'[.;\n!?]',source['quote']):
   if isinstance(name,str) and re.search(re.escape(name),clause,re.I):observed.extend(_norm(x['text']) for x in _numeric(clause,req))
 if observed and wanted not in observed:return {'status':'POTENTIAL_ENTITY_QUANTITY_MISMATCH','semantic_support':'NOT_COVERED','observed_tokens':observed,'provenance':'CLAUSE_ASSOCIATION_HEURISTIC_NOT_ENTAILMENT'}
 return {'status':'PROPOSED_SAME_ENTITY_ASSOCIATION' if observed else 'UNRESOLVED_ASSOCIATION','semantic_support':'UNKNOWN','observed_tokens':observed,'provenance':'CLAUSE_ASSOCIATION_HEURISTIC_NOT_ENTAILMENT'}

def align(profile,candidate,data,documents):
 """Native requirement-keyed objects provide a demonstrable output structure.
 Model-generated prose/Boolean properties never acquire hard authority.
 """
 texts={d['source_id']:d['context'] for d in documents};cat=build_catalogue(texts);supports={s['requirement_id']:s for s in data.get('requirement_support',[])};rows=[];native=isinstance(candidate,dict)
 for req in profile['requirements']:
  parents=[supports[p] for p in req['parent_requirement_ids'] if p in supports];refs=sorted({ref for p in parents for ref in p.get('supporting_span_ids',[])});evidence=[];errors=[]
  for ref in refs:
   try:evidence.append(resolve_span(ref,texts,cat))
   except ValueError as exc:errors.append(str(exc))
  if native:
   exists=req['requirement_id'] in candidate;value=candidate.get(req['requirement_id']);fragments=[{'text':value,'start':None,'end':None,'provenance':'EXPLICIT_STRUCTURED_CANDIDATE_COMPONENT'}] if exists and value is not None else []
  else:fragments=propose_fragments(candidate,req,data,len(profile['requirements'])>1)
  # All fragment proposals remain visible when selection is ambiguous.
  chosen=fragments[0] if len(fragments)==1 else None;compatibility=_compatible(chosen,req,native)
  exact_parent=len(parents)==1 and len(profile['requirements'])==len(profile['legacy_requirements']) and req['answer_type']==next((p.get('answer_kind') for p in profile['legacy_requirements'] if p['requirement_id']==parents[0]['requirement_id']),None)
  model_flags={key:parents[0].get(key) for key in ['support_status','complete_answer','referent_resolved','relation_and_qualifiers_supported','identity_identified','answer_form']} if len(parents)==1 else {}
  row={'requirement_id':req['requirement_id'],'requirement':req,'candidate_fragment':chosen,'candidate_fragments':fragments,'type_compatible':compatibility,'type_compatibility_is_entailment':False,'supporting_span_ids':refs,'resolved_supporting_spans':evidence,'span_errors':errors,'proposed_relation':req['relation_or_operation'],'required_qualifiers':req['qualifiers'],'semantic_parent_mapping':'EXACT_TYPED_REQUIREMENT' if exact_parent else 'COARSE_INHERITED_ASSESSMENT','model_semantic_properties':model_flags,'structured_candidate':native,'explicit_component_missing':native and not fragments,'provenance':{'query':'EXACT_QUERY_SPAN','fragment':'STRUCTURED_APPLICATION_VALUE' if native else 'EXACT_CANDIDATE_OFFSETS_WITH_PROPOSED_TYPE','support':'FROZEN_LLM_REFERENCE_ASSERTION','semantic_association':'UNRESOLVED_UNLESS_SEPARATELY_ESTABLISHED'}}
  rows.append(row)
 by={r['requirement_id']:r for r in rows}
 for row in rows:
  parent_fragments=[f for rid in row['requirement']['depends_on'] for f in by[rid]['candidate_fragments']];row['dependency_association']=association(row['requirement'],row['candidate_fragment'],parent_fragments,row['resolved_supporting_spans'])
  if not native:
   for fragment in row['candidate_fragments']:
    if not isinstance(candidate,str) or candidate[fragment['start']:fragment['end']]!=fragment['text']:raise ValueError('RDA_INVALID_CANDIDATE_OFFSET')
 return {'version':'rda-alignment-1.0','requirements':rows,'native_structured_candidate':native,'candidate':candidate,'independent_entailment_proof':False}
