import pytest
from .score import selection_metric,answer_citations,aggregate
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue

def test_relevance_not_answer_sufficiency():
 m=selection_metric({'cite_1'},['YES'],['RELATED-INFORMATION']);assert m['precision']==1 and m['recall']==1;assert m['correctness_distribution']=={'RELATED-INFORMATION':1};assert 'FULL' not in m

def test_empty_citations_precision_undefined_recall_zero():
 m=selection_metric(set(),['YES','NO'],['ANSWER-THE-QUESTION','']);assert m['precision'] is None;assert m['recall']==0;assert m['f1']==0

def test_unknown_relevance_not_made_negative():
 m=selection_metric({'cite_1'},[''],['UNKNOWN']);assert m['fp']==0;assert m['selected_unknown_relevance']==1;assert m['precision'] is None

def test_citation_parser_distinguishes_invalid_and_numbers():
 cat=build_catalogue({'view-0001':'supplied text'});mapping=[{'original_marker':'cite_1','source_id':'view-0001'}];valid,invalid=answer_citations('In 2025 [cite_1] [cite_99] [view-0001:span-0000] [view-0001:span-0009] [12]',mapping,cat);assert valid=={'cite_1'};assert invalid==['cite_99','view-0001:span-0009']

def test_support_not_implicit_public_citations():
 cat=build_catalogue({'view-0001':'text'});assert answer_citations('A supported but uncited answer.',[{'original_marker':'cite_1','source_id':'view-0001'}],cat)==(set(),[])

def test_micro_metrics():
 m=aggregate([selection_metric({'cite_1'},['YES','YES'],['UNKNOWN','UNKNOWN']),selection_metric({'cite_2'},['YES','NO'],['UNKNOWN',''])]);assert m['tp']==1 and m['fp']==1 and m['fn']==2;assert m['micro_precision']==.5;assert m['micro_recall']==1/3;assert m['micro_f1']==.4
