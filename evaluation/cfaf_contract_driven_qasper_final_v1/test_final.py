"""Synthetic eligibility, sampling and frozen-system identity safeguards."""
import copy,json,pytest
from .mapping import label,valid_annotation,source_integrity
from .selection import choose
from . import measured_c as impl
from .systems import STANDARD_PROMPT,guarded_a
from evaluation.cfaf_contract_driven_2h_v1 import measured_c as old
from evaluation.cfaf_contract_driven_2h_v1.systems import STANDARD_PROMPT as oldprompt
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.cfaf_target_claim_alignment_v1.test_target_claim import case

def paper():return {'title':'Synthetic trial','abstract':'A controlled study.','full_text':[{'section_name':'Result','paragraphs':['The archive is not released.']}],'figures_and_tables':[]}
def ann(un=False,yn=None,spans=None,free='',ev=None):return {'answer':{'unanswerable':un,'yes_no':yn,'extractive_spans':spans or [],'free_form_answer':free,'evidence':[] if ev is None else ev,'highlighted_evidence':[]}}
def question(aa):return {'question_id':'synthetic-id','question':'Is the archive released?','answers':aa}

@pytest.mark.parametrize('answer',[ann(yn=False,ev=['The archive is not released.']),ann(yn=True,ev=['The archive is not released.']),ann(spans=['not released'],ev=['The archive is not released.']),ann(free='It is not released.',ev=['The archive is not released.'])])
def test_structural_answer_types_do_not_invent_semantic_truth(answer):
 v=label('unit',paper(),question([answer]));assert v['mode']=='FULL';assert v['tier']=='S'

def test_boolean_disagreement_is_unknown():
 a=ann(yn=False,ev=['The archive is not released.']);b=ann(yn=True,ev=['The archive is not released.']);assert label('unit',paper(),question([a,b]))['reasons']==['CONTRADICTORY_BOOLEAN_ANSWERS']

def test_mixed_answerability_is_unknown():
 assert label('unit',paper(),question([ann(True),ann(yn=False)]))['mode']=='UNKNOWN'

@pytest.mark.parametrize('aa',[[],[ann()],[ann(True,yn=False)],[{'answer':{'unanswerable':'false'}}]])
def test_invalid_or_missing_answers_never_silently_discarded(aa):assert label('unit',paper(),question(aa))['mode']=='UNKNOWN'

def test_single_and_multiple_unanswerable_tiers():
 assert label('unit',paper(),question([ann(True)]))=={'mode':'CFAF','tier':'S','reasons':[]};assert label('unit',paper(),question([ann(True),ann(True)]))['tier']=='M'

@pytest.mark.parametrize('ev,reason',[([], 'NO_ORIGINAL_TEXT_EVIDENCE'),(['FLOAT SELECTED: Table 1'],'UNAVAILABLE_NONTEXTUAL_EVIDENCE'),(['Text absent from source.'],'ORIGINAL_TEXT_EVIDENCE_UNREPRESENTED')])
def test_unsupported_original_evidence_is_unknown(ev,reason):
 v=label('unit',paper(),question([ann(yn=False,ev=ev)]));assert v['mode']=='UNKNOWN';assert reason in v['reasons']

def test_float_is_not_rescued_by_caption_or_alternate_paragraph():
 p=paper();p['figures_and_tables']=[{'file':'table.png','caption':'Table 1'}];v=label('unit',p,question([ann(yn=False,ev=['The archive is not released.','FLOAT SELECTED: Table 1'])]));assert v['mode']=='UNKNOWN'

def test_whitespace_only_normalization_for_evidence():
 assert label('unit',paper(),question([ann(yn=False,ev=['The archive\n is not released.'])]))['mode']=='FULL'

def test_incomplete_paper_is_unknown_even_for_unanswerable():
 p=paper();p['full_text']=[];assert label('unit',p,question([ann(True)]))['reasons']==['SOURCE_INTEGRITY_INVALID']

def test_paper_sampling_reserves_other_class_without_duplicates():
 pool={m:[{'paper_id':str(i),'question_id':m+str(i)} for i in range(5)] for m in ['FULL','CFAF']};a,unique=choose(pool,2);b,_=choose(pool,2);assert a==b;assert unique;assert len({r['paper_id'] for r in a})==4

def test_clustered_fallback_keeps_requested_questions():
 pool={m:[{'paper_id':'one','question_id':m+str(i)} for i in range(3)] for m in ['FULL','CFAF']};r,unique=choose(pool,2);assert not unique;assert len(r)==4;assert len({r['question_id'] for r in r})==4

def test_original_algorithms_and_realization_calls_unchanged():
 assert impl.run_governed is old.run_governed;assert impl.TopLevelModeSelectionStage is old.TopLevelModeSelectionStage;assert impl.ANALYSIS_SCHEMA==old.ANALYSIS_SCHEMA;assert STANDARD_PROMPT==oldprompt
 p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);out=impl.run_governed(case(),p);assert [k for k,_ in p.calls]==['semantic_analysis','semantic_cfaf'];assert len(out['internal_trace']['stage_sequence'])==8

def test_gold_field_rejected_before_network(monkeypatch):
 from .provider import StudyProvider
 monkeypatch.setenv('OPENAI_API_KEY','synthetic-key');p=StudyProvider();r=impl.project_case(case())
 with pytest.raises(ValueError,match='BENCHMARK_FIELD'):p.call(r,'standard_rag','',{**r.public(),'unanswerable':True},512)

def test_260_durable_cap_before_network(monkeypatch,tmp_path):
 from . import provider
 monkeypatch.setenv('OPENAI_API_KEY','synthetic-key');(tmp_path/'local').mkdir();(tmp_path/'local/api_requests.jsonl').write_text('{}\n'*260,encoding='utf-8');monkeypatch.setattr(provider,'ROOT',tmp_path);p=provider.StudyProvider()
 with pytest.raises(RuntimeError,match='260_API_ATTEMPT_CAP'):p._post_json('/chat/completions',{})
