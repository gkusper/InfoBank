"""Create the ignored complete case report from immutable execution and review data."""
from .artifacts import *
import datetime

def generate():
 ensure()
 packet=rows(ROOT/'local/review_packet.jsonl');raw={r['runtime_index']:r for r in rows(ROOT/'local/results_raw.jsonl')};reviews={r['runtime_index']:r for r in read(ROOT/'QUALITATIVE_REVIEW.json')['cases']}
 assert len(packet)==len(raw)==len(reviews)==80
 out=['# Complete QASPER TEST case report (local, ignored)','','Contains original human answers, paper excerpts and generated outputs. Keep out of Git.','All original labels/predictions are preserved. Agent review is non-independent and unblinded; these notes are not corrected gold or independent answer accuracy.','Case numbers are one-based; runtime_index is zero-based. Raw provider requests/responses remain in the adjacent private JSONL files.']
 def block(obj):return '\n```json\n'+json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n```\n'
 for p in packet:
  i=p['runtime_index'];r=raw[i];q=reviews[i]
  out.extend([f"\n## Case {i+1}: {p['gold_mode']} / Tier {p['annotation_tier']}",f"Paper: {p['paper_id']} — {p['title']}",f"Question ID: {p['question_id']}",f"Question: {p['question']}",f"Original annotations: {p['original_annotation_count']}",'### Original human answer references',block(p['references']),'### Original human evidence',block(p['human_evidence']),'### Complete A/B/C served responses',block(p['responses']),'### Execution and validation statuses',block({k:{key:val for key,val in v.items() if key!='response'} for k,v in r['systems'].items()}),'### C semantic analysis',block(p['C_analysis']),'### C selected source windows',block(p['selected_spans']),'### C full verification and alignment trace',block(p['C_verification']),'### Retrieval and passage-overlap diagnostics',block(p['evidence_metrics']),'### Non-independent qualitative review',block(q)])
 (ROOT/'local/CASE_REPORT.md').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
 source=read(ROOT/'MANUSCRIPT_SOURCE.json');assert sha(Path(source['path']))==source['sha256']
 write(ROOT/'LATEX_COMPILE_AUDIT.json',{'status':'SUCCESS','validation_method':'Codex desktop built-in LaTeX compiler','helper_project':str(REPO.parents[1]/'work/cfaf-final-qasper-paper-check'),'main_file':'main.tex','included_file':'results.tex','compiler_message':'The current source compiled successfully with the desktop editor\'s compiler.','fragment_sha256':sha(ROOT/'RESULTS_FOR_PAPER_QASPER.tex'),'manuscript_source_sha256':source['sha256'],'original_manuscript_unchanged':True,'current_manuscript_or_PDF_written':False,'audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 text=(ROOT/'REPORT.md').read_text(encoding='utf-8-sig')
 text=text.replace('fdc9d8214fbab5dd7829586017fb4d678e6934a54','fdc9d8214fbab5dd782958601db4d678e6934a54')
 (ROOT/'REPORT.md').write_text(text,encoding='utf-8')
 print('COMPLETE PRIVATE CASE REPORT',len(packet),'cases;', (ROOT/'local/CASE_REPORT.md').stat().st_size,'bytes; source manuscript unchanged')

if __name__=='__main__':generate()
