"""Public-context bridge to the finalized, unchanged semantic-integration-v2.1."""
import hashlib,json
from evaluation.infobank_semantic_integration_v2.integration import run_governed
from evaluation.infobank_semantic_integration_v2.provider import GovernedProvider

RUNTIME_FIELDS={'perturbed_query','perturbed_context'}
FORBIDDEN_FIELDS={'expected_rag_behavior','implementation_reasoning','perturbation_class','intensity','original_query','original_context','original_answers','verifier_votes','lever_selected','id','source_question_group'}


def canonical(x):return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':'))
def validate_runtime(row):
 if set(row)!=RUNTIME_FIELDS:raise ValueError('Runtime requires exactly perturbed_query and perturbed_context.')
 if any(not isinstance(row[k],str) for k in RUNTIME_FIELDS) or not row['perturbed_query'].strip():raise ValueError('Runtime fields must be text; query must be nonempty.')

def authorize_runtime(rows,authorization):
 if not authorization.get('selection_approved') or len(rows)!=authorization['row_count'] or len(rows)!=20:raise ValueError('Unauthorized runtime cardinality.')
 for i,row in enumerate(rows):
  validate_runtime(row)
  if authorization['rows'][i] != {'runtime_index':i,'input_sha256':hashlib.sha256(canonical(row).encode()).hexdigest()}:raise ValueError('Runtime selection authorization mismatch.')


def public_case(row,index):
 validate_runtime(row)
 if type(index) is not int or not 0<=index<20:raise ValueError('Runtime index outside frozen pilot.')
 return {'case_id':f'runtime-{index:04d}','pair_id':'unpaired','family':'public-context','variant':'none','query':row['perturbed_query'],
 'sources':[{'source_id':'local-public-passage','source_type':'Document','title':'Supplied public passage','content':row['perturbed_context'],'metadata':{},'retrieved':True,'access_mode':'FULL','existence_visibility':'PUBLIC','purpose_compatibility':'compatible','security_status':'clean'}]}


def all_keys(x):
 if isinstance(x,dict):
  for key,value in x.items():yield key;yield from all_keys(value)
 elif isinstance(x,list):
  for value in x:yield from all_keys(value)


class PilotProvider(GovernedProvider):
 def __init__(self,out):super().__init__(out,75);self.case_calls=[]
 def call(self,request,kind,prompt,payload,limit):
  if set(all_keys(payload)) & FORBIDDEN_FIELDS:raise ValueError('Benchmark annotation in model input.')
  result=super().call(request,kind,prompt,payload,limit)
  self.case_calls.append({'kind':kind,'raw_content':result.content,'model':result.model,'input_tokens':result.input_tokens,'output_tokens':result.output_tokens,'latency_ms':result.latency_ms,'response_id':result.response_id})
  return result
