import copy,json,hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from .prepare_dataset import filter_a,filter_b,eligible,metadata_only,select_indices,boundaries,SOURCE,ROOT,QUOTAS,SEED
from .public_adapter import validate_runtime,public_case,authorize_runtime,canonical,PilotProvider,FORBIDDEN_FIELDS,all_keys
from .score import score
from evaluation.infobank_semantic_integration_v2.metadata_binding import project_case
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span
from evaluation.refusalbench_span_fix_v1.contracts import validate_response

@pytest.mark.parametrize('text,result',[
 ('contradiction',True),('a CONTRADICTION!',True),('non-contradiction case',True),
 ('contradictory',False),('contradictions',False),('conflict',False),('selfcontradiction',False),('',False),(None,False)])
def test_exact_word_filter(text,result):assert filter_a({'implementation_reasoning':text})==result
@pytest.mark.parametrize('record',[
 {'expected_rag_behavior':'REFUSE_CONTRADICTORY_CONTEXT'}, {'perturbation_class':'P-Contradiction'}])
def test_official_category_exclusion(record):assert filter_b(record) and not eligible(record)
def test_related_words_do_not_broaden_filter():assert eligible({'implementation_reasoning':'contradictory contradictions conflict','expected_rag_behavior':'ANSWER_CORRECTLY','perturbation_class':'P-Other'})

def test_original_and_selection_preserved():
 report=json.loads((ROOT/'filtering_report.json').read_text());assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==report['original_file_sha256'];assert report['original_records']==1600
 cases=[json.loads(x) for x in (ROOT/'selected_cases.jsonl').read_text().splitlines()];assert len(cases)==20;assert all(eligible(c) for c in cases)
def test_seed_group_and_holdout_constraints():
 metadata=metadata_only(SOURCE);allowed,used,reserved,_=boundaries();indices,pool=select_indices(metadata,allowed,used);manifest=json.loads((ROOT/'filtered_selection_manifest.json').read_text());assert indices==[r['dataset_index'] for r in manifest['selected_records']];assert len({metadata[i]['source_id'] for i in indices})==20
 assert all(str(metadata[i]['source_id']) in allowed and str(metadata[i]['source_id']) not in reserved and metadata[i]['id'] not in used and eligible(metadata[i]) for i in indices)
def test_filtered_records_cannot_be_selected():
 metadata=metadata_only(SOURCE);allowed,used,_,_=boundaries();indices,_=select_indices(metadata,allowed,used)
 assert not {i for i,m in enumerate(metadata) if filter_a(m) or filter_b(m)}&set(indices)
def test_runtime_authorization_rejects_excluded_substitution():
 rows=[json.loads(x) for x in (ROOT/'runtime_inputs.jsonl').read_text().splitlines()];auth=json.loads((ROOT/'runtime_authorization.json').read_text());authorize_runtime(rows,auth);rows[0]={'perturbed_query':'Unauthorized replacement','perturbed_context':'Another passage.'}
 with pytest.raises(ValueError,match='authorization mismatch'):authorize_runtime(rows,auth)
@pytest.mark.parametrize('key',sorted(FORBIDDEN_FIELDS))
def test_annotation_fields_rejected(key):
 with pytest.raises(ValueError):validate_runtime({'perturbed_query':'Who won?','perturbed_context':'A passage.',key:'label'})
def test_public_adapter_is_latest_not_older_pipeline():
 from .public_adapter import run_governed
 assert run_governed.__module__=='evaluation.infobank_semantic_integration_v2.integration'
def test_no_invented_binding_or_gold_in_adapter():
 request=project_case(public_case({'perturbed_query':'Who built the tower?','perturbed_context':'The tower was built by Lea.'},0));assert request.documents[0]['context']=='The tower was built by Lea.';assert request.documents[0]['view_kind']=='content';assert request.view_bindings[0]['binding_status']=='UNRESOLVED';assert not (set(all_keys(request.public()))&FORBIDDEN_FIELDS)
def test_query_profiler_unchanged_and_unresolved_not_tuned():
 from evaluation.infobank_semantic_integration_v2.query_profile import profile_query
 assert profile_query('Who built the tower?')['resolution']=='UNRESOLVED'
def test_span_resolution_against_exact_public_context():
 req=project_case(public_case({'perturbed_query':'Which code is stated?','perturbed_context':'The code is Q7.'},0));docs={d['source_id']:d['context'] for d in req.documents};cat=build_catalogue(docs)
 for ref in cat.spans:assert resolve_span(ref,docs,cat)['quote']=='The code is Q7.'
 with pytest.raises(ValueError):resolve_span('original-label-bearing-record',docs,cat)
def test_nonempty_output_contract():
 base={'answer':'Cannot determine from this passage.','top_level_mode':'CFAF','fulfilment_status':'NONE','realization':'ABSTAIN','public_reason_class':'EVIDENTIAL','next_step_codes':[]};assert not validate_response(json.dumps(base));base['answer']=None;assert validate_response(json.dumps(base))
def test_balanced_zero_cost_references_and_errors_not_refusals():
 cases=[{'id':str(i),'source_id':str(i),'expected_rag_behavior':'ANSWER_CORRECTLY' if i<10 else 'REFUSE_AMBIGUOUS_QUERY','perturbed_context':'A passage.'} for i in range(20)];records,systems=score(cases,[])
 assert systems['always_full']['accuracy']==systems['always_cfaf']['accuracy']==.5
 assert systems['semantic_cfaf']['accuracy']==0 and systems['semantic_cfaf']['parser_or_runtime_or_validation_errors']==20
