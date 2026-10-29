"""Small extraction of the historical first-failing-assessment selector principle.
Original: evaluation/wolala2026/pipeline.py @ bfd80bbfe2ccbb251da46bdc22b791dad5b9341f.
Nonempty-request and execution/policy checks belong to the caller.
"""
def select(assessments):
    failing=[a for a in assessments if not a['can_fulfil_request']]
    if not failing:return {'mode':'FULL','fulfilment':'FULL','reason':None,'realization':None,'permitted_output':'REQUESTED_OUTPUT'}
    first=failing[0]
    return {'mode':'CFAF','fulfilment':'RESTRICTED' if first['permitted_content'] not in {'NONE','EXCLUDED'} else 'NONE','reason':first['reason_class'],'realization':first.get('cfaf_realization') or 'ABSTAIN','permitted_output':first['permitted_content']}
