"""Query-only, conservative English request profiling. No source/policy inputs."""
import re
from dataclasses import dataclass,asdict

FIELDS={
 'file_type':r'\b(file type|document type|file format|format|mime type)\b',
 'created_at':r'\b(creation date|created date|date created|created_at|when.{0,60}created)\b',
 'modified_at':r'\b(last modified|modification date|modified_at)\b',
 'author':r'\b(author|authored|written by)\b',
 'owner':r'\b(owner|ownership)\b',
 'size_bytes':r'\b(file size|size in bytes)\b'}

def normalize(text):return ' '.join(re.findall(r'[\w-]+',text.casefold()))

def target_from_query(query):
 text=query.strip().rstrip('?.!')
 matches=list(re.finditer(r'\b(?:for|about|regarding|of)\s+(.+)$',text,re.I))
 if matches:
  target=matches[-1].group(1).strip(' "\'')
  if not re.search(r'\b(and|or|their|its|those|these)\b',target,re.I):return target
 match=re.search(r'\bwhen\s+was\s+(.+?)\s+created\b',text,re.I)
 return match.group(1).strip(' "\'') if match else None


def profile_query(query):
 if not isinstance(query,str) or not query.strip():raise ValueError('Nonempty query required')
 q=query.casefold();types=[];fields=[name for name,pattern in FIELDS.items() if re.search(pattern,q)]
 def add(kind):
  if kind not in types:types.append(kind)
 if re.search(r'\b(how many|number of|count of|count the|tally of|total number)\b',q):add('AGGREGATE_COUNT')
 if re.search(r'\b(average|mean)\b',q):add('AGGREGATE_AVERAGE')
 if re.search(r'\b(sum|summed|combined amount|total amount|total cost|total revenue|total expenditure|total spending)\b',q):add('AGGREGATE_SUM')
 if re.search(r'\b(percentage|percent|proportion|median|distribution|maximum|minimum)\b',q):add('AGGREGATE_OTHER')
 if re.search(r'\b(each|list|enumerate|identify|which (?:specific )?(?:ticket|record|person|employee|transaction|payment)|who received)\b',q) or ('individual' in q and not any(t.startswith('AGGREGATE_') for t in types)):add('INDIVIDUAL_RECORD')
 if fields or re.search(r'\bmetadata\b',q):add('METADATA_LOOKUP')
 if re.search(r'\b(body|body text|contents|full text|document text)\b',q):add('DOCUMENT_CONTENT')
 if re.search(r'\b(next action|next step|deadline|must i do|should i do|need to do|recorded action)\b',q):add('ACTION_LOOKUP')
 if not types and re.search(r'\b(token|code|document|memo|report|says?|states?)\b',q):add('DOCUMENT_CONTENT')
 if not types:types=['UNRESOLVED']
 unresolved='UNRESOLVED' in types or ('METADATA_LOOKUP' in types and not fields)
 requirements=[{'requirement_id':f'request-{i+1}','request_type':kind,'metadata_fields':fields if kind=='METADATA_LOOKUP' else []} for i,kind in enumerate(types)]
 return {'version':'query-profile-v2.1','resolution':'UNRESOLVED' if unresolved else 'RESOLVED','requirements':requirements,'query_target':target_from_query(query),'method':'query_text_only_conservative_grammar'}
