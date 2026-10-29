from common import *
from score import summary
x=read(OUT/'latency_comparison.json');u=read(OUT/'api_usage.json');data=rows(OUT/'local/paired_raw.jsonl');common=[r for r in data if all(r['systems'][s]['usage'].get('model') for s in ['C1','C2']) and all(r['systems'][s]['usage']['attempts']==1 for s in ['C1','C2'])]
for s,v in x['systems'].items():
 print(s,{k:{w:round(z,3) if isinstance(z,float) else z for w,z in v[k].items()} for k in ['selected_case_end_to_end_ms','provider_ms','proposal_bytes','gate_ms','render_ms','public_validation_ms']})
print('COMMON26', {s:{'e2e':summary([r['systems'][s]['system_end_to_end_ms'] for r in common]),'provider':summary([r['systems'][s]['usage']['provider_ms'] for r in common])} for s in ['C1','C2']})
print('REDUCTIONS', {k:100*(1-u['both_reported_common_totals']['C2'][k]/u['both_reported_common_totals']['C1'][k]) for k in ['input_tokens','output_tokens','provider_ms']})
print('ATTEMPT_TIME_RANGE',min(e['started_epoch'] for e in rows(OUT/'local/api_ledger.jsonl') if e['event']=='ATTEMPT'),max(e['started_epoch'] for e in rows(OUT/'local/api_ledger.jsonl') if e['event']=='ATTEMPT'))
