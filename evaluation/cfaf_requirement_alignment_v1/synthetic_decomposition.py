"""Explicitly authored structural development cases; no empirical holdout claim."""
from .artifacts import *
from .requirement_decomposition import decompose,validate
CASES=[
 ('Who engraved the tablet?',['NAMED_IDENTITY']),('When did the vessel depart?',['DATE_TIME']),
 ('Who collected the most shells and how many shells did she collect?',['NAMED_IDENTITY','COUNT']),
 ('Who built the station and when was it opened?',['NAMED_IDENTITY','DATE_TIME']),
 ('Report the count and average waiting time.',['COUNT','QUANTITY']),
 ('What are the height and color of the monument?',['QUANTITY','FACT']),
 ('List all participants in the expedition.',['DESCRIPTION']),('Who was the first curator?',['NAMED_IDENTITY']),
 ('Who was the last curator?',['NAMED_IDENTITY']),('Where did it happen?',['LOCATION']),
 ('What color is the First National Bank logo?',['FACT']),
 ('Who composed the theme and when was it recorded and how many copies were sold?',['NAMED_IDENTITY','DATE_TIME','COUNT']),
 ('What year was the academy founded?',['DATE_TIME']),('What is the sum of amounts?',['QUANTITY']),
 ('How much did the instrument cost?',['QUANTITY']),('How long did the journey last?',['DURATION']),
 ('What file type and creation date are recorded for green atelier?',['METADATA','DATE_TIME'])]

def run():
 records=[]
 for i,(query,expected) in enumerate(CASES):
  p=decompose(query);actual=[r['answer_type'] for r in p['requirements']];records.append({'index':i,'query':query,'expected_answer_types':expected,'actual_answer_types':actual,'exact_requirement_count_correct':len(actual)==len(expected),'exact_type_sequence_correct':actual==expected,'valid_query_spans_and_ids':validate(p),'profile':p,'scope':'Author-created synthetic structural development regression, no independent validation'})
 for r in records:append(ROOT/'synthetic_decomposition_cases.jsonl',r)
 summary={'n':len(records),'complete_type_and_count_matches':sum(r['exact_type_sequence_correct'] for r in records),'valid_query_provenance':sum(r['valid_query_spans_and_ids'] for r in records),'not_independent':True,'model_calls':0};write(ROOT/'synthetic_decomposition_summary.json',summary);print(summary)
 if summary['complete_type_and_count_matches']!=len(records):raise RuntimeError('Structural regression mismatch')
if __name__=='__main__':run()
