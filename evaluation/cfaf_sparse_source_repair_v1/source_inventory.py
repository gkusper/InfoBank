"""Application-owned complete authorized inventory, independent of model roles."""
from dataclasses import dataclass,asdict
import hashlib,json
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span
from evaluation.cfaf_target_claim_alignment_v1.integration import assert_safe_payload

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
@dataclass(frozen=True)
class SourceEntry:
 view_id:str
 access_mode:str
 view_kind:str
 source_sha256:str
 span_ids:tuple
 spans:tuple
 source_date:str|None
 original_marker:str|None
@dataclass(frozen=True)
class SourceInventory:
 request_signature:str
 entries:tuple
 inventory_sha256:str
 def public(self):return {'request_signature':self.request_signature,'inventory_sha256':self.inventory_sha256,'sources':[{k:v for k,v in asdict(e).items() if k!='original_marker'} for e in self.entries]}
 def private(self):return {'request_signature':self.request_signature,'inventory_sha256':self.inventory_sha256,'sources':[asdict(e) for e in self.entries]}

def build_inventory(request,private_mapping=()):
 assert_safe_payload(request,request.public());documents={d['source_id']:d['context'] for d in request.documents};cat=build_catalogue(documents);mapping=list(private_mapping)
 if any(set(m)!={'source_id','original_marker'} and not {'source_id','original_marker'}<=set(m) for m in mapping):raise ValueError('INVALID_PRIVATE_MAPPING')
 if any(m['source_id'] not in documents or not isinstance(m['original_marker'],str) or not m['original_marker'] for m in mapping):raise ValueError('UNAUTHORIZED_PRIVATE_MARKER_MAPPING')
 if len({m['source_id'] for m in mapping})!=len(mapping) or len({m['original_marker'] for m in mapping})!=len(mapping):raise ValueError('AMBIGUOUS_PRIVATE_MARKER_MAPPING')
 markers={m['source_id']:m['original_marker'] for m in mapping};entries=[]
 for d in request.documents:
  source=d['source_id'];spans=[s for s in cat.spans.values() if s.source_id==source];date=None
  try:
   header=json.loads(d['context'].split('\n',1)[0]);date=header.get('date') if isinstance(header,dict) else None
  except (ValueError,TypeError):pass
  entries.append(SourceEntry(source,{'content':'FULL','metadata':'METADATA','aggregate':'AGGREGATE'}[d['view_kind']],d['view_kind'],cat.source_hashes[source],tuple(s.span_id for s in spans),tuple((s.span_id,s.start_offset,s.end_offset,s.source_sha256) for s in spans),date,markers.get(source)))
 native=tuple(entries);signature=request.signature();return SourceInventory(signature,native,digest({'request_signature':signature,'entries':[asdict(e) for e in native]}))

def validate_inventory(inventory,request):
 if not isinstance(inventory,SourceInventory):raise ValueError('UNTRUSTED_SOURCE_INVENTORY')
 mapping=[{'source_id':e.view_id,'original_marker':e.original_marker} for e in inventory.entries if e.original_marker]
 if build_inventory(request,mapping)!=inventory:raise ValueError('STALE_SOURCE_INVENTORY')
 return True

def resolve_inventory_span(reference,inventory,request):
 validate_inventory(inventory,request);documents={d['source_id']:d['context'] for d in request.documents};return resolve_span(reference,documents,build_catalogue(documents))
