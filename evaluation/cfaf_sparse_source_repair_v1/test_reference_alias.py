import json,pytest
from .reference_alias_ablation import parse_alias
from .source_inventory import build_inventory
from .test_sparse import sample

def test_numeric_padding_is_exact_existing_span_alias():
 c,r,d=sample(1);ref=d['supporting_spans'][0];d['supporting_spans']=['view-0001:span-0'];a,data,audit=parse_alias(json.dumps(d),r,build_inventory(r));assert a.valid;assert data['supporting_spans']==[ref];assert audit['experimental_R1_repairs'][0]['method']=='EXACT_NUMERIC_INDEX_FORMAT_ALIAS'
@pytest.mark.parametrize('ref',['view-0001:span-4','view-9999:span-0','view-0001:span-999999'])
def test_alias_cannot_invent_or_choose_nearest(ref):
 c,r,d=sample(1);d['supporting_spans']=[ref];a,data,audit=parse_alias(json.dumps(d),r,build_inventory(r));assert not a.valid;assert not audit['experimental_R1_repairs'];assert data['supporting_spans']==[ref]
def test_padding_repair_does_not_repair_semantic_completeness():
 c,r,d=sample(1);d['supporting_spans']=['view-0001:span-0'];d['requirement_support'][0]['complete_answer']=False;a,data,audit=parse_alias(json.dumps(d),r,build_inventory(r));assert a.valid;assert data['requirement_support'][0]['complete_answer'] is False
