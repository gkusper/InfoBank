import json,copy,time
import pytest
from .deadline import snapshot,ensure,elapsed
from .exposure import ROOT,metadata_only,SOURCE,eligible,stable
from .scoring import common_errors,reason_category
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
from evaluation.infobank_semantic_integration_v2.metadata_binding import project_case

def test_task_clock_is_monotonic_and_deadline():
 a=elapsed();b=elapsed();assert b>=a;assert ensure('test',1)>0;assert snapshot()['remaining_seconds']<=3600

def test_exposure_reconstruction_and_ceiling():
 ledger=json.loads((ROOT/'exposure_ledger.json').read_text());assert ledger['eligible_records']==1234;assert ledger['maximum_exposed_eligible_records']==617;assert ledger['prior_unique_exposed_records_all_categories']==82;assert ledger['prior_exposed_unique_eligible_records']==70
 assert len({e['id'] for e in ledger['entries']})==len(ledger['entries']);assert ledger['cumulative_exposed_eligible_records']<=617
 assert not set(ledger['allowed_development_source_groups'])&(set(ledger['reserved_source_groups'])|set(ledger['untouched_source_groups']))

def test_metadata_filter_and_authorized_pool():
 metadata=metadata_only(SOURCE);assert sum(eligible(m) for m in metadata)==1234

def test_stable_hashes():assert stable('record')==stable('record') and stable('record')!=stable('other')
@pytest.mark.parametrize('mode,status,valid',[('FULL','FULL',True),('FULL','NONE',False),('CFAF','FULL',False),('CFAF','NONE',True),('CFAF','RESTRICTED',True)])
def test_uniform_cross_field_validation(mode,status,valid):
 response={'answer':'A user visible response.','top_level_mode':mode,'fulfilment_status':status,'realization':None,'public_reason_class':None,'next_step_codes':[]};assert bool(common_errors(json.dumps(response))) is not valid

def test_reason_specificity():
 assert reason_category('The query is ambiguous.')=='REFUSE_AMBIGUOUS_QUERY'
 assert reason_category('The query relies on an unsupported premise.')=='REFUSE_FALSE_PREMISE_IN_QUERY'
 assert reason_category('The currently usable evidence does not support this.') is None

def test_initial_pipeline_preserved():
 from .versions.v00.implementation import run_governed
 assert run_governed.__module__=='evaluation.infobank_semantic_integration_v2.integration'

def test_public_context_not_privileged_binding():
 request=project_case(public_case({'perturbed_query':'Who painted the mural?','perturbed_context':'Lea painted it.'},0));assert request.view_bindings[0]['binding_status']=='UNRESOLVED';assert request.documents[0]['context']=='Lea painted it.'
