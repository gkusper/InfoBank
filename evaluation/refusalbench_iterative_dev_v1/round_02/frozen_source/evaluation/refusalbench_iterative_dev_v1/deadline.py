"""One monotonic task deadline, shared by all workers and bounded subprocesses."""
import datetime as dt,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class DeadlineReached(RuntimeError):pass

def limits():return json.loads((ROOT/'time_limits.json').read_text())
def elapsed():return time.monotonic()-limits()['monotonic_start']
def remaining():return limits()['hard_deadline_after_seconds']-elapsed()
def ensure(operation,expected_seconds=1,new_api=False):
 l=limits();used=elapsed()
 if used>=l['hard_deadline_after_seconds'] or remaining()<expected_seconds+5:raise DeadlineReached('Hard deadline margin prevents '+operation)
 if new_api and used>=l['stop_new_api_after_seconds']:raise DeadlineReached('55-minute API-start cutoff reached')
 return remaining()
def run_process(args,cwd,expected_seconds=30,timeout_seconds=90,env=None):
 budget=ensure('subprocess '+str(args[0]),expected_seconds)
 return subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=min(timeout_seconds,budget-5))
def snapshot():return {'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'elapsed_seconds':elapsed(),'remaining_seconds':remaining(),'report_priority':elapsed()>=limits()['prioritize_report_after_seconds'],'new_api_allowed':elapsed()<limits()['stop_new_api_after_seconds']}
