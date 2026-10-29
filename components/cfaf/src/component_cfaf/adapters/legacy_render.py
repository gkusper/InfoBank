"""Compatibility renderer for the isolated, saved-contract ablation only."""
def realize_legacy(contract):
    full=contract['mode']=='FULL'
    return {'answer':contract['answer_candidate'] if full else contract['public_reason_text'],'top_level_mode':contract['mode'],'fulfilment_status':contract['fulfilment_status'],'realization':contract['realization'],'public_reason_class':contract['public_reason_class'],'next_step_codes':[]}
