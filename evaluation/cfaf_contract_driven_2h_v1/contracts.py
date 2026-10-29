"""Minimal framework-independent boundary contracts, reusing trusted validators."""
from dataclasses import dataclass
import hashlib,json
from evaluation.cfaf_sparse_source_repair_v1.source_inventory import build_inventory
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import validate_response
from evaluation.cfaf_target_claim_alignment_v1.integration import assert_safe_payload
@dataclass(frozen=True)
class RequestContract:
 query:str
 projection_signature:str
 @classmethod
 def from_request(cls,request):
  assert_safe_payload(request,request.public());return cls(request.query,request.signature())
@dataclass(frozen=True)
class PermittedEvidenceContract:
 request_signature:str
 inventory_sha256:str
 view_hashes:tuple
 @classmethod
 def from_request(cls,request):
  inventory=build_inventory(request);return cls(request.signature(),inventory.inventory_sha256,tuple((e.view_id,e.access_mode,e.source_sha256) for e in inventory.entries))
@dataclass(frozen=True)
class FulfilmentDecision:
 mode:str
 verification_status:str
 reason_code:str|None
 def __post_init__(self):
  if self.mode not in {'FULL','CFAF'}:raise ValueError('INVALID_MODE')
  if self.verification_status=='OPERATIONAL_FAILURE' and self.mode=='FULL':raise ValueError('OPERATIONAL_FAILURE_CANNOT_BE_FULL')
@dataclass(frozen=True)
class PublicResponseContract:
 response_json:str
 @classmethod
 def from_response(cls,response):
  encoded=json.dumps(response,sort_keys=True,ensure_ascii=True);errors=validate_response(encoded)
  if errors:raise ValueError(','.join(errors))
  return cls(encoded)
