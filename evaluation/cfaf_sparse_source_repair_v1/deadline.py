"""Persistent wall and monotonic task deadline; never resets at process restart."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class DeadlineReached(RuntimeError):pass
def state():return json.loads((ROOT/'task_state.json').read_text())
def elapsed():
 s=state();return max(time.time()-s['start_epoch'],time.monotonic()-s['start_monotonic'])
def ensure(operation='work',expected_seconds=1,new_api=False,large_work=False):
 s=state();e=elapsed()
 if e+expected_seconds+5>=s['hard_seconds']:raise DeadlineReached('Hard task deadline: '+operation)
 if large_work and e>=s['large_work_stop_seconds']:raise DeadlineReached('45-minute large-work cutoff')
 if new_api and e>=s['new_api_stop_seconds']:raise DeadlineReached('55-minute API cutoff')
 return s['hard_seconds']-e
