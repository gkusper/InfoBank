"""Exact deterministic reference normalization; no nearest-span repair."""
import re
from .source_inventory import validate_inventory,resolve_inventory_span

def normalize_reference(reference,inventory,request,allow_repair=True):
 validate_inventory(inventory,request)
 if isinstance(reference,str):
  try:return reference,None,resolve_inventory_span(reference,inventory,request)
  except ValueError as original:
   if not allow_repair:raise
   match=re.fullmatch(r'(cite_\d+):span-(\d{4})',reference)
   if match:
    mapped=[e for e in inventory.entries if e.original_marker==match.group(1)]
    if len(mapped)==1:
     candidate=mapped[0].view_id+':span-'+match.group(2)
     span=resolve_inventory_span(candidate,inventory,request)
     return candidate,{'original':reference,'normalized':candidate,'method':'EXACT_ORIGINAL_MARKER_EQUIVALENT_SPAN'},span
   raise original
 if not allow_repair or not isinstance(reference,dict):raise ValueError('INVALID_REFERENCE_REPRESENTATION')
 allowed={'source_id','quote','start','end','source_sha256'}
 if not set(reference)<=allowed or not reference.get('source_id'):raise ValueError('INVALID_REFERENCE_HINT')
 matches=[]
 for entry in inventory.entries:
  if entry.view_id!=reference['source_id']:continue
  if 'source_sha256' in reference and reference['source_sha256']!=entry.source_sha256:raise ValueError('REFERENCE_SOURCE_HASH_MISMATCH')
  if 'quote' in reference:
   text=next(d['context'] for d in request.documents if d['source_id']==entry.view_id);q=reference['quote']
   if not isinstance(q,str) or not q or text.find(q)<0 or text.find(q,text.find(q)+1)>=0:raise ValueError('QUOTE_NOT_UNIQUE_OR_ABSENT')
  for ref in entry.span_ids:
   span=resolve_inventory_span(ref,inventory,request)
   if 'quote' in reference and span['quote']!=reference['quote']:continue
   if 'start' in reference and (type(reference['start']) is not int or span['start']!=reference['start']):continue
   if 'end' in reference and (type(reference['end']) is not int or span['end']!=reference['end']):continue
   if not ('quote' in reference or 'start' in reference and 'end' in reference):continue
   matches.append((ref,span))
 if len(matches)!=1:raise ValueError('REFERENCE_RESOLUTION_NOT_UNIQUE')
 ref,span=matches[0];method='UNIQUE_EXACT_CATALOGUE_QUOTE' if 'quote' in reference else 'EXACT_CATALOGUE_OFFSETS'
 return ref,{'original':reference,'normalized':ref,'method':method},span
