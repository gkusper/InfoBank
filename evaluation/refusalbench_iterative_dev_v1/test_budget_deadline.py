import json,time
import pytest
from . import deadline
from . import provider_v2

def test_no_new_api_after_55_minutes(monkeypatch):
 monkeypatch.setattr(deadline,'limits',lambda:{'monotonic_start':time.monotonic()-3301,'hard_deadline_after_seconds':3600,'stop_new_api_after_seconds':3300})
 with pytest.raises(deadline.DeadlineReached,match='55-minute'):deadline.ensure('API',1,new_api=True)

def test_hard_deadline_or_expected_duration_blocks_work(monkeypatch):
 monkeypatch.setattr(deadline,'limits',lambda:{'monotonic_start':time.monotonic()-3580,'hard_deadline_after_seconds':3600,'stop_new_api_after_seconds':3300})
 with pytest.raises(deadline.DeadlineReached,match='Hard deadline'):deadline.ensure('long subprocess',30)

def test_task_cap_counts_durable_attempts_before_network(tmp_path,monkeypatch):
 monkeypatch.setattr(provider_v2,'ROOT',tmp_path);(tmp_path/'global_api_requests.jsonl').write_text(''.join(json.dumps({'attempt':i})+'\n' for i in range(360)))
 provider=provider_v2.BoundedProvider.__new__(provider_v2.BoundedProvider)
 with pytest.raises(RuntimeError,match='360 attempt'):provider._post_json('/chat/completions',{})
