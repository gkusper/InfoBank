"""R1 experimental numeric-format aliases, evaluated AFTER frozen Phase B.
Never applied silently to the primary run. No case-specific rules or gold input.
"""
import copy,json,re
from .source_inventory import validate_inventory
from .sparse_source_assessment import parse_sparse

def canonicalize_numeric_aliases(data,inventory,request):
 validate_inventory(inventory,request);out=copy.deepcopy(data);known={ref for e in inventory.entries for ref in e.span_ids};repairs=[]
 containers=[(out,k) for k in ['supporting_spans','contradicting_spans']]
 containers +=[(r,'grounding_span_ids') for r in out.get('source_assessments',[])]
 containers +=[(r,'supporting_span_ids') for r in out.get('requirement_support',[])]
 for obj,key in containers:
  for i,ref in enumerate(obj.get(key,[])):
   if not isinstance(ref,str) or ref in known:continue
   match=re.fullmatch(r'(view-\d{4}):span-(\d{1,12})',ref)
   if not match:continue
   candidate=match.group(1)+':span-'+str(int(match.group(2))).zfill(4)
   if candidate not in known:continue
   obj[key][i]=candidate;repairs.append({'field':key,'index':i,'original':ref,'normalized':candidate,'method':'EXACT_NUMERIC_INDEX_FORMAT_ALIAS','inventory_sha256':inventory.inventory_sha256})
 return out,repairs

def parse_alias(raw,request,inventory):
 data=json.loads(raw);normalized,repairs=canonicalize_numeric_aliases(data,inventory,request);a,final,audit=parse_sparse(json.dumps(normalized),request,inventory,True);audit['experimental_R1_repairs']=repairs;return a,final,audit

def evaluate():
 from .artifacts import ROOT,REPO,read,rows,write,append
 from .gate_controls import assess
 from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
 from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
 from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance
 from .source_inventory import build_inventory
 import collections
 if (ROOT/'reference_alias_ablation.json').exists():raise RuntimeError('R1 already saved')
 results=rows(ROOT/'live_paired_results.jsonl');runtime=rows(ROOT/'runtime_inputs.jsonl');selection=read(ROOT/'selection_manifest.json');records=[]
 for record,inp,selected in zip(results,runtime,selection['records']):
  out=record['outcome'];request=request_for(inp['case'],out);inventory=build_inventory(request,inp['mapping']);raw=next(c['content'] for c in record['api_calls'] if c['kind']=='semantic_analysis');a,data,audit=parse_alias(raw,request,inventory);v=assess(request,a,data,'T3',trusted_provenance(request,False));mode=selector(v,request,data);records.append({'runtime_index':record['runtime_index'],'sample_id':selected['sample_id'],'primary_valid':out['semantic_valid'],'R1_valid':a.valid,'primary_mode':out['selected_mode'],'R1_mode':mode,'R1_errors':audit['errors'],'repairs':audit['experimental_R1_repairs'],'verification_outcome':v['verification_outcome'],'new_generated_response':False});append(ROOT/'reference_alias_ablation_raw.jsonl',{'runtime_index':record['runtime_index'],'normalized_data':data,'audit':audit,'verification':v})
 write(ROOT/'reference_alias_ablation.json',{'configuration':'R1 supplemental deterministic reference-format ablation on frozen fresh outputs','after_primary_phase_B':True,'primary_outputs_and_runtime_unchanged':True,'model_calls':0,'not_independent':True,'numeric_alias_rule':'Canonicalize decimal span-index formatting only when the exact equivalent ID exists in the same authorized source inventory. No nearest-ID selection.','valid':sum(r['R1_valid'] for r in records),'modes':dict(collections.Counter(r['R1_mode'] for r in records)),'repaired_reference_occurrences':sum(len(r['repairs']) for r in records),'cases':records})
 print('R1',sum(r['R1_valid'] for r in records),'valid;',sum(len(r['repairs']) for r in records),'exact format-alias repairs;',collections.Counter(r['R1_mode'] for r in records))
if __name__=='__main__':evaluate()
