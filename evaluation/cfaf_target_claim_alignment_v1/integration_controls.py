"""Controlled shadow extensions to B3; new diagnostics do not alter its gate."""
import copy
from .metadata_value_typing import decompose_fixed
from .trusted_target_resolution import catalogue_from_request,resolve,validate_resolution,legacy_resolution
from .claim_evidence_alignment import align_claims
from evaluation.cfaf_requirement_alignment_v1.requirement_alignment import align
from evaluation.cfaf_requirement_alignment_v1.rec_v2 import assess as baseline_assess,reason_details as baseline_reason
CONFIGURATIONS={'A0','B3','T1','T2','T3'}

def _legacy_target(request):return legacy_resolution(request)

def assess(request,assessment,data,configuration='T3',provenance=None,semantic_overrides=None):
 if configuration not in CONFIGURATIONS:raise ValueError('TARGET_CLAIM_CONFIGURATION_UNKNOWN')
 if semantic_overrides:raise ValueError('SECOND_VERIFIER_DISABLED')
 base_config='A0' if configuration=='A0' else 'B3';base=baseline_assess(request,assessment,data,base_config,provenance)
 if configuration in {'A0','B3'}:return {**base,'configuration':configuration,'target_claim':None,'baseline_reference_configuration':base_config}
 typed_profile=decompose_fixed(request.query,request.query_profile);new_alignment=align(typed_profile,data.get('answer_candidate'),data,request.documents)
 trusted=any(getattr(p,'origin','')=='original_synthetic_ingestion_fixture' for p in (provenance or {}).values()) or any(b['binding_status']=='TRUSTED_QUERY_TARGET' for b in request.view_bindings)
 catalogue=catalogue_from_request(request,trusted);new_target=resolve(request,catalogue);validate_resolution(new_target,request,catalogue)
 target=new_target if configuration in {'T1','T3'} else _legacy_target(request)
 claims=align_claims(typed_profile,new_alignment,data,request,target) if configuration in {'T2','T3'} else None
 # Retain the old gate and its provenance; publish the corrected typed profile
 # and new diagnostics separately so no upstream or authority change is hidden.
 result=copy.deepcopy(base);result['configuration']=configuration;result['baseline_reference_configuration']='B3';result['target_claim']={'typed_requirements_profile':typed_profile,'requirement_alignment':new_alignment,'trusted_target':new_target if configuration in {'T1','T3'} else None,'claim_alignment':claims,'target_used_for_claims':target if claims else None,'shadow_only':True,'type_fix_has_gate_authority':False,'new_hard_enforcement':False}
 result['change_cause']='NO_GATE_CHANGE_SHADOW_DIAGNOSTICS';result['typed_requirements_profile']=typed_profile
 if result['issues']!=base['issues'] or result['validated_request_fulfilment']!=base['validated_request_fulfilment']:raise ValueError('SHADOW_EXTENSION_CHANGED_BASELINE_GATE')
 return result

def reason_details(result,request,data):
 return baseline_reason({**result,'configuration':result.get('baseline_reference_configuration','B3')},request,data)
