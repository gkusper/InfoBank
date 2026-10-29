"""Offline non-independent review packets. Private benchmark text stays local."""
from common import *
import sys
from audit import prepare
from component_cfaf.compact import CompactProposal,expand

def packet(start,end):
 ensure();verify_freeze();data=rows(OUT/'local/paired_raw.jsonl');items=rows(ROOT/'results/local/inputs.jsonl');events=rows(OUT/'local/api_ledger.jsonl')
 for row in data[start:end]:
  i=row['index'];item=items[i];_,(req,ev,_)=prepare(item);c=row['systems']['C2'];out={'case':i+1,'query':item['query'],'C1_mode_status':[row['systems']['C1']['response']['mode'],row['systems']['C1']['execution_status']],'C2_response':c['response'],'reason':c['result']['decision'],'source_windows':[]}
  if i<20:
   out['source_windows']=[{'id':v.source_id,'kind':v.view_kind,'text':v.text[:1600]} for v in ev.views]
  else:
   for citation in c['response'].get('citations',[]):
    v=next(v for v in ev.views if v.source_id==citation['source_id']);out['source_windows'].append({'id':v.source_id,'text':v.text[max(0,citation['start']-150):min(len(v.text),citation['end']+200)]})
  if c['execution_status']!='SUCCESS':
   rid=c['usage'].get('response_id');matches=[e for e in events if e['event']=='RESULT' and e['kind']=='C2' and (e.get('response') or {}).get('id')==rid]
   if matches:
    content=matches[0]['response']['choices'][0]['message']['content'];compact=CompactProposal.model_validate_json(content);out['raw_compact']=compact.model_dump(mode='json')
    try:expand(compact,req);out['expand']='PASS'
    except Exception as e:out['expand_error']=str(e)
  print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':packet(int(sys.argv[1]),int(sys.argv[2]))
