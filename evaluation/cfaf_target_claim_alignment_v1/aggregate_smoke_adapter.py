"""Structured-input smoke reuse of the inspected main aggregate executor."""
import math
from .vendor.aggregate_core import AggregateConfig,AggregateContribution,execute_aggregate

def execute(contributions,policy,operation='mean',k=3):
 if type(k) is not int or k<2:raise ValueError('AGGREGATE_UNSAFE_THRESHOLD')
 permitted=[]
 for c in contributions:
  if policy.get(c.get('source_id')) not in {'FULL','AGGREGATE'}:continue
  if type(c.get('value')) not in {int,float} or not math.isfinite(c['value']):raise ValueError('STRUCTURED_FINITE_NUMERIC_CONTRIBUTION_REQUIRED')
  permitted.append(AggregateContribution(c['source_id'],c['contributor_id'],c['value']))
 # Only the existing CFAF FULL/AGGREGATE classes permit contribution inclusion.
 decisions={sid:{'FULL':'full','AGGREGATE':'aggregate','METADATA':'metadata','DENY':'deny'}.get(mode,'deny') for sid,mode in policy.items()}
 raw=execute_aggregate(permitted,decisions,AggregateConfig(k_threshold=k,operation=operation))
 if raw['aggregate'] is None:return {'status':'UNAVAILABLE','answer':'A governed aggregate result is unavailable for this request.','generator_context':{},'citations':[],'public_trace':{'aggregate_available':False}}
 value=raw['aggregate']['value'];return {'status':'AVAILABLE','answer':raw['safe_output'],'generator_context':{'operation':operation,'value':value},'citations':[],'public_trace':{'aggregate_available':True}}
