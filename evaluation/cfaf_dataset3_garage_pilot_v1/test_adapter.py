import json,random,pytest
from .adapter import runtime_projection,RUNTIME_KEYS,passage,GOLD_KEYS,INPUT_BUDGET
from .provider import BoundedProvider
from .artifacts import *
from evaluation.cfaf_target_claim_alignment_v1 import integration as impl
PUBLIC={'question':'What color is the fictional sample token?','question_date':'1 January 2025','grounding':[{'age':'unknown','date':'not defined','provider':'ent','cite_1':'The fictional sample token is blue.'},{'age':'unknown','date':'not defined','provider':'web','cite_2':'A different sample token is red.'}]}
def test_exact_sampling():
 m=read(ROOT/'dataset3_selection_manifest.json');assert random.Random(20261028).sample(range(2366),10)==m['indices_zero_based'];assert len(set(m['indices_zero_based']))==10
@pytest.mark.parametrize('key',sorted(GOLD_KEYS|{'sample_id','expected_mode'}))
def test_gold_keys_rejected(key):
 with pytest.raises(ValueError,match='EXACT_RUNTIME_WHITELIST'):runtime_projection({**PUBLIC,key:'GOLD-CANARY'})
def test_neutral_sources_complete_passages_metadata():
 r=runtime_projection(PUBLIC);request=impl.project_case(r['case']);assert len(request.documents)==2;assert r['included_count']==2 and not r['altered_context'];assert [d['source_id'] for d in request.documents]==['view-0001','view-0002'];assert all(s['access_mode']=='FULL' for s in r['case']['sources']);assert PUBLIC['grounding'][0]['cite_1'] in request.documents[0]['context'];assert r['mapping'][0]['original_marker']=='cite_1';assert r['analysis_input_token_upper_bound']<=INPUT_BUDGET
@pytest.mark.parametrize('provider',['ent','web'])
def test_provider_is_metadata_not_governance(provider):
 r=runtime_projection({**PUBLIC,'grounding':[dict(PUBLIC['grounding'][0],provider=provider)]});assert r['case']['sources'][0]['access_mode']=='FULL';assert r['case']['sources'][0]['source_type']=='Document'
def test_no_secret_gold_identifiers_in_payload():
 r=runtime_projection(PUBLIC);p=impl.project_case(r['case']).public();assert not(set(p)&GOLD_KEYS);assert 'private-garage-source' not in json.dumps(p)
def test_corrupt_marker_rejected():
 with pytest.raises(ValueError):passage({'cite_3':'bad'},0)
def test_unknown_source_metadata_rejected():
 with pytest.raises(ValueError):passage({'cite_1':'text','evidence_correct':'YES'},0)
def test_budget_deterministic_prefix():
 public={**PUBLIC,'grounding':[{'cite_1':'x'*1000},{'cite_2':'z'*100000},{'cite_3':'last'}]};r=runtime_projection(public);assert r['included_count']==1;assert r['omitted_original_markers']==['cite_2','cite_3'];assert r['altered_context'];assert runtime_projection(public)==r
def test_oversize_first_fails_without_resampling():
 with pytest.raises(ValueError,match='FIRST_PASSAGE'):runtime_projection({**PUBLIC,'grounding':[{'cite_1':'x'*100000}]})
def test_original_selector_import():
 assert impl.TopLevelModeSelectionStage.__module__=='evaluation.wolala2026.pipeline';assert len(list(impl.StageName))==8
def test_runtime_gold_file_separation():
 runtime=rows(ROOT/'runtime_inputs.jsonl');gold=rows(ROOT/'gold_annotations.jsonl');assert len(runtime)==len(gold)==10
 for r,g in zip(runtime,gold):
  assert 'sample_id' not in r;assert not set(r)&GOLD_KEYS;assert r['runtime_index']==g['runtime_index'];assert r['original_grounding_count']==15
