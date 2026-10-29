"""Offline reporting only; no inference or changes to the frozen runtime."""
from common import *
from score import summary

def table(headers,data):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in data])
def main():
 ensure();verify_freeze();api=read(OUT/'api_usage.json');lat=read(OUT/'latency_comparison.json');raw=rows(OUT/'local/paired_raw.jsonl');scored=rows(OUT/'local/scored_private.jsonl');mode=read(OUT/'mode_confusion.json')
 common=[r for r in raw if all(r['systems'][s]['usage'].get('model') and r['systems'][s]['usage']['attempts']==1 for s in ['C1','C2'])]
 lat['both_reported_common_latency']={s:{'end_to_end_ms':summary([r['systems'][s]['system_end_to_end_ms'] for r in common]),'provider_ms':summary([r['systems'][s]['usage']['provider_ms'] for r in common])} for s in ['C1','C2']};write(OUT/'latency_comparison.json',lat)
 api['both_reported_common_reductions_percent']={k:100*(1-api['both_reported_common_totals']['C2'][k]/api['both_reported_common_totals']['C1'][k]) for k in ['input_tokens','output_tokens','provider_ms']};api['failed_request_usage_unknown_not_zero']=True;write(OUT/'api_usage.json',api)
 findings={2:('REQUEST_INCOMPLETE','A limitation statement is accepted as the requested value.'),8:('REQUEST_INCOMPLETE','Absence of an action is accepted as complete fulfilment.'),12:('NATIVE_LABEL_SCOPE_REVIEW','Native FULL retained; participants are partly named by surname, with completeness a scope question.'),16:('NATIVE_LABEL_SCOPE_REVIEW','Native FULL retained; the passage does not establish the requested edition qualifier.'),18:('REQUEST_INCOMPLETE','Public text omits the requested person although the cited passage and private typed value identify one.'),19:('UNSUPPORTED_ASSERTION','Actual infrastructure facts do not establish a necessary counterfactual consequence.'),20:('TEMPORAL_GEOGRAPHIC_OVERGENERALIZATION','A national century-scale trend is inferred from limited state examples.'),23:('REQUEST_INCOMPLETE','Listing hosting options gives little comparison of organizational needs.'),25:('ENTITY_SUBJECT_RELATION_MISMATCH','A general acquisition practice replaces a risk-management account for the particular obligation.'),27:('MISSING_QUALIFIERS','Forecasts are merged without attribution and a material condition on the extreme scenario.'),28:('UNVERIFIED_CAUSAL_SUPPORT','Several cited passages describe adverse news; causation of the requested rally is not established.'),30:('UNVERIFIED_CAUSAL_SUPPORT','Selection and an operating model do not establish the causal explanation of approval.')}
 quality=[]
 for r in raw:
  c=r['systems']['C2'];case=r['index']+1;flag,note=findings.get(case,('NO_SPECIFIC_FLAG_IN_LIMITED_REVIEW','No specific issue recorded; this is not a correctness certification.'));n=len(c['response'].get('citations',[]))
  if c['execution_status']!='SUCCESS':flag='OPERATIONAL_WITHHELD';note='No substantive answer released; operational fallback is not evidential CFAF success.'
  quality.append({'index':r['index'],'case_number_one_based':case,'system':'C2','observation':flag,'note':note,'mechanically_valid_public_citations':n,'semantic_support':'NOT_INDEPENDENTLY_VERIFIED' if n else 'NOT_APPLICABLE_NO_PUBLIC_CITATION','exhaustive_semantic_review':False})
 write(OUT/'qualitative_review.json',{'reviewer':'Codex, also implementer; non-independent, unblinded','scope':'All 30 C2 public outcomes screened using the query and permitted passage text (native cases) or cited text and surrounding windows (GaRAGe). Not exhaustive every-source adjudication. No new A/B/C1 answer-quality scoring.','not_a_quality_accuracy_estimate':True,'native_gold_unchanged':True,'answer_quality_axes':{'request_completeness':'Specific concerns in cases 2, 8, 18, 23, 25','unsupported_assertions':'Counterfactual necessity, broad trend and causal explanations in 19, 20, 28, 30','entity_subject_mismatch':'Specific obligation replaced by general practice in case 25','temporal_geographic_overgeneralization':'Case 20; scenario qualifications matter in 27','missing_qualifiers':'16 (label scope), 27, 28, 30','valid_citations':'33 C2 public links mechanically revalidated','citations_with_unverified_semantic_support':'31 model-attributed, 2 application-structured; none independently semantically verified'},'cases':quality})
 ref=read(OUT/'reference_error_analysis.json');ref['case_numbering']='JSON indices are zero-based; REPORT uses index+1.';ref['C2_generic_validation_error_offline_diagnosis']={'index':3,'subcause':'INVALID_MISSING_REQUIREMENT','method':'Reparse saved compact response with the frozen expand function offline; no new call or output edit.','detail':'Natural-language text in missing instead of a valid requirement ID.'};write(OUT/'reference_error_analysis.json',ref)
 native=[]
 for d,label in [('dataset1','InfoBank'),('dataset2','RefusalBench-NQ')]:
  for s,v in mode['cohorts'][d]['systems'].items():native.append([label,s,f"{v['correct']}/10",f"{v['balanced_accuracy']:.0%}",f"{v['FULL_recall']:.0%}",f"{v['CFAF_recall']:.0%}",v['unnecessary_refusal'],v['failure_to_restrict'],v['operational_failures']])
 resources=[];phases=[];proposals=[]
 for s in ['A','C1','C2']:
  u=api['systems'][s];v=lat['systems'][s];e=v['selected_case_end_to_end_ms'];p=v['provider_ms'];b=v['proposal_bytes'];resources.append([s,u['attempts'],f"{u['input_tokens']:,}",f"{u['output_tokens']:,}",f"{p['sum']/1000:.3f}",f"{e['sum']/1000:.3f}",f"{e['median']/1000:.3f}",f"{e['max']/1000:.3f}"]);phases.append([s]+[f"{v[k]['sum']:.3f}" for k in ['gate_ms','render_ms','public_validation_ms']]);proposals.append([s,b['N'],b['sum'],b['median'],b['max'],f"{p['median']/1000:.3f}",f"{p['max']/1000:.3f}"])
 pairs=[]
 for r in scored:
  def label(s):
   v=r['scored'][s];return v['mode'] if v['status']=='SUCCESS' else 'OP:'+v['status']
  change='no binary gold'
  if r['dataset']!='garage':
   c1=r['scored']['C1']['correct'];c2=r['scored']['C2']['correct'];change='both correct' if c1 and c2 else 'C2 only correct' if c2 else 'C1 only correct' if c1 else 'neither correct'
  pairs.append([r['index']+1,{'dataset1':'InfoBank','dataset2':'RefNQ','garage':'GaRAGe'}[r['dataset']],label('A'),label('B'),label('C1'),label('C2')])
 rendered={'{{NATIVE_TABLE}}':table(['Cohort','System','Correct','Balanced accuracy','FULL recall','CFAF recall','Unnecessary refusal','Failure to restrict','Operational'],native),'{{RESOURCE_TABLE}}':table(['System','Attempts','Reported input','Reported output','Provider sum s','E2E sum s','E2E median s','E2E max s'],resources),'{{PHASE_TABLE}}':table(['System','Gate ms','Renderer ms','Public validator ms'],phases),'{{PROPOSAL_TABLE}}':table(['System','Attempt N','JSON bytes sum','Median bytes','Max bytes','Provider median s','Provider max s'],proposals),'{{PAIR_TABLE}}':table(['Case','Cohort','A','B','Fresh C1','C2'],pairs)}
 p=OUT/'REPORT.md';text=p.read_text(encoding='utf-8-sig')
 for key,value in rendered.items():text=text.replace(key,value)
 assert '{{' not in text;p.write_text(text,encoding='utf-8');print('Report tables, qualitative diagnostics and comparable-pair metrics complete.')
if __name__=='__main__':main()
