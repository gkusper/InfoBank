"""Differential tests import legacy code only in the test process."""
import sys,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from evaluation.wolala2026.pipeline import TopLevelModeSelectionStage,RunContext
from evaluation.wolala2026.labels import ClaimAssessment,PipelineState,ReasonClass,CFAFRealization
from component_cfaf.adapters.legacy_selector import select

def test_first_failing_assessment_equivalence():
    tested=0
    for size in [1,2,3,4]:
        for flags in itertools.product([False,True],repeat=size):
            for permitted in ['NONE','EXCLUDED','METADATA_ONLY','AGGREGATE_ONLY','CONTENT']:
                for reason in [ReasonClass.EVIDENTIAL,ReasonClass.GOVERNANCE_PRIVACY]:
                    assessments=[ClaimAssessment(str(i),'SUPPORTED' if okay else 'MISSING',[],[],okay,permitted,'detail','detail',okay,'accepted' if okay else None,reason,'TEST',CFAFRealization.ABSTAIN) for i,okay in enumerate(flags)]
                    state=PipelineState(case_id='synthetic',query_id='q',query='q',claim_assessments=assessments)
                    old=TopLevelModeSelectionStage().run(state,RunContext(case={})).mode_decision
                    new=select([{'can_fulfil_request':a.can_fulfil_request,'permitted_content':a.permitted_content,'reason_class':a.reason_class.value,'cfaf_realization':a.cfaf_realization.value} for a in assessments])
                    assert new['mode']==old.mode.value and new['fulfilment']==old.fulfilment_status.value
                    assert new['reason']==(old.reason_class.value if old.reason_class else None)
                    assert new['realization']==(old.cfaf_realization.value if old.cfaf_realization else None)
                    assert new['permitted_output']==old.permitted_output;tested+=1
    assert tested==300
