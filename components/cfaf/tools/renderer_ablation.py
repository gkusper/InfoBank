"""Zero-call comparison of historical generated realizations and exact contract copying."""
from common import *
from component_cfaf.adapters.legacy_render import realize_legacy

def main():
    ensure();verify_freeze();state=read(STATE);source=Path(state['worktrees'][0]['path']);study=source/'evaluation/cfaf_contract_driven_2h_v1';garage=source/'evaluation/cfaf_dataset3_garage_pilot_v1';hashes=git_json('evaluation/cfaf_contract_driven_2h_v1/raw_artifact_hashes.json')['files'];assert sha(study/'api_requests.jsonl')==hashes['api_requests.jsonl']
    requests=rows(study/'api_requests.jsonl');grequests=rows(garage/'api_requests.jsonl');selected=read(ROOT/'results/exposure_manifest.json')['records'];public=[]
    old_rows={'dataset1':rows(study/'dataset1_results_raw.jsonl'),'dataset2':rows(study/'dataset2_results_raw.jsonl'),'garage':rows(garage/'results.jsonl')}
    for r in selected:
        dataset=r['dataset'];i=r['source_runtime_index'];old=old_rows[dataset][i];out=old.get('C_outcome',old.get('outcome',{}));pool=grequests if dataset=='garage' else requests
        calls=[q for q in pool if q['kind']=='semantic_cfaf' and q['runtime_index']==i and (dataset=='garage' or q.get('dataset')==dataset)]
        record={'index':r['index'],'dataset':dataset,'new_analysis_calls':0,'new_generation_calls':0,'old_semantic_valid':out.get('semantic_valid'),'mode_changed':False}
        if len(calls)!=1 or out.get('semantic_valid') is not True:
            record['status']='NOT_APPLICABLE_NO_SAVED_VALID_PROPOSAL_AND_CONTRACT';public.append(record);continue
        user=json.loads(calls[0]['payload']['messages'][1]['content']);contract=user['response_contract'];rendered=realize_legacy(contract);oldresponse=out.get('raw_responses',out.get('responses',{})).get('semantic_cfaf');expected=realize_legacy(contract)
        exact=lambda v:isinstance(v,dict) and all(v.get(k)==expected[k] for k in expected)
        record.update(status='REPLAYED',old_response_matches_contract=exact(oldresponse),deterministic_response_matches_contract=exact(rendered),contract_sha256=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest(),model_answer_accuracy='NOT_EVALUATED',citation_support_accuracy='NOT_EVALUATED')
        append(ROOT/'results/local/renderer_ablation_raw.jsonl',{'index':r['index'],'contract':contract,'old_raw_response':oldresponse,'deterministic_response':rendered,'original_assessment':out['semantic_assessment']});public.append(record)
    write(ROOT/'results/renderer_ablation.json',{'status':'COMPLETED','new_LLM_calls':0,'selected':30,'replayed':sum(r['status']=='REPLAYED' for r in public),'old_contract_matches':sum(r.get('old_response_matches_contract',False) for r in public),'new_contract_matches':sum(r.get('deterministic_response_matches_contract',False) for r in public),'mode_selection_or_semantic_accuracy_change_claimed':False,'citation_ids_in_old_public_contract':'NOT_INSTRUMENTED','scope':'Saved old assessment and response contract, historical 512-token generated realization versus compatibility renderer exact copying. Does not evaluate the new one-call semantic schema.','source_request_ledger_hashes':{'study':sha(study/'api_requests.jsonl'),'original_garage_pilot':sha(garage/'api_requests.jsonl')},'cases':public})
    print('RENDERER ABLATION',sum(r['status']=='REPLAYED' for r in public),'eligible saved contracts; zero new model calls')
if __name__=='__main__':main()
