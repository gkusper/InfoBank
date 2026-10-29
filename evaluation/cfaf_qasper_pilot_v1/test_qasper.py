"""Synthetic adapter, annotation, leakage and immutable-pipeline regression checks."""
import copy,json,pytest
from .selection import label,annotation_mode
from .adapter import project,paragraphs,rank,INPUT_BUDGET
from . import measured_c as impl
from evaluation.cfaf_contract_driven_2h_v1 import measured_c as previous
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.cfaf_target_claim_alignment_v1.test_target_claim import case

def annotation(unanswerable=False,spans=None,free='',yn=None):return {'answer':{'unanswerable':unanswerable,'extractive_spans':spans or [],'free_form_answer':free,'yes_no':yn}}
@pytest.mark.parametrize('a,expected',[(annotation(yn=False),'FULL'),(annotation(yn=True),'FULL'),(annotation(spans=['known']),'FULL'),(annotation(free='known'),'FULL'),(annotation(True),'CFAF'),(annotation(),'UNKNOWN'),(annotation(True,yn=False),'UNKNOWN'),(annotation(spans=['x'],yn=True),'UNKNOWN'),({'answer':{'unanswerable':'false'}},'UNKNOWN')])
def test_original_answer_types(a,expected):assert annotation_mode(a)[0]==expected

def test_question_unanimity():
 assert label({'answers':[annotation(yn=False),annotation(spans=['known'])]})[0]=='FULL'
 assert label({'answers':[annotation(True),annotation(yn=False)]})[0]=='UNKNOWN'
 assert label({'answers':[]})[0]=='UNKNOWN'
 assert label({'answers':[annotation(True),annotation(True)]})[0]=='CFAF'

def public():return {'question':'What material was used?','title':'Synthetic experiment','abstract':'The paper studies materials.','full_text':[{'section_name':'Method','paragraphs':['The experiment used birch.','An unrelated observation.']}],'figures_and_tables':[{'caption':'Table 1: Materials comparison.'}]}

def test_gold_rejected_and_whole_paper_retained():
 p=public();r=project(p);assert r['retrieval_method']=='WHOLE_PAPER';assert r['included_paragraphs']==3;assert r['analysis_input_token_upper_bound']<=INPUT_BUDGET
 assert all(x in r['case']['sources'][0]['content'] for x in ['Synthetic experiment','The paper studies','birch','Table 1'])
 for field in ['answers','unanswerable','evidence','expected_mode','question_id']:
  with pytest.raises(ValueError):project({**p,field:True})

def test_local_fts5_ranking_and_ties():
 ps=paragraphs(public());a=rank(ps,'birch');assert a[0]==0;assert a==rank(ps,'birch');assert sorted(a)==list(range(3))

def test_current_pipeline_is_byte_equivalent_logic():
 for k in ['GOVERNED_PROMPT','CFAF_PROMPT','ANALYSIS_SCHEMA','GENERATION_SCHEMA']:assert getattr(impl,k)==getattr(previous,k)
 assert impl.TopLevelModeSelectionStage is previous.TopLevelModeSelectionStage
 p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);out=impl.run_governed(case(),p);assert [k for k,_ in p.calls]==['semantic_analysis','semantic_cfaf'];assert len(out['internal_trace']['stage_sequence'])==8

def test_provider_rejects_gold_before_network(monkeypatch):
 from .provider import StudyProvider
 monkeypatch.setenv('OPENAI_API_KEY','synthetic-unit-key');p=StudyProvider();r=impl.project_case(case())
 with pytest.raises(ValueError,match='BENCHMARK_FIELD'):p.call(r,'standard_rag','',dict(r.public(),sample_id='no'),512)
 with pytest.raises(ValueError,match='STANDARD_RAG_CONTAMINATION'):p.call(r,'standard_rag','',dict(r.public(),semantic_assessment={}),512)

def test_retrieval_budget_retains_whole_paragraphs_original_order(monkeypatch):
 from . import adapter
 p=public();p['full_text'][0]['paragraphs']=['Background filler. '*200,'Birch material was used.','Additional background. '*200]
 base=adapter.bound(adapter.make_case(p['question'],adapter.render(p,[])[0]));monkeypatch.setattr(adapter,'INPUT_BUDGET',base+3500)
 a=adapter.project(p);b=adapter.project(p);assert a==b;assert a['retrieval_method']=='SQLITE_FTS5_BM25';assert a['included_paragraphs']<a['available_paragraphs'];assert a['paragraph_mapping']==sorted(a['paragraph_mapping'],key=lambda x:x['key']);assert 'Birch material' in a['case']['sources'][0]['content'];assert a['analysis_input_token_upper_bound']<=base+3500

@pytest.mark.parametrize('field',['unanswerable','extractive_spans','yes_no','free_form_answer','evidence','highlighted_evidence','annotation_id','worker_id','question_id','paper_id','derived_gold_mode','answers'])
def test_qasper_specific_fields_blocked_before_network(monkeypatch,field):
 from .provider import StudyProvider
 monkeypatch.setenv('OPENAI_API_KEY','synthetic-unit-key');p=StudyProvider();r=impl.project_case(case())
 with pytest.raises(ValueError,match='BENCHMARK_FIELD'):p.call(r,'standard_rag','',dict(r.public(),**{field:False}),512)
