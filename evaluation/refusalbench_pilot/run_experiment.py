"""First-ten pilot. Run prepare, audit, generate, score in separate processes.

Generation reads only the two-field runtime file. Labels and original IDs are
joined exclusively in the score command after generation. No retries/tuning.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.error

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from evaluation.refusalbench_pilot.adapter import ADAPTER_VERSION, adapt_runtime, validate_runtime
from evaluation.wolala2026.adapters import ALL_MODES, adapter_for_mode
from evaluation.wolala2026.pipeline import assert_pipeline_invariants, run_pipeline
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.wolala2026.retrieval import build_retrieval_snapshot

HERE = Path(__file__).resolve().parent
DATASET = 'aashiqmuhamed/RefusalBench-NQ'
PROTECTED = ['evaluation/wolala2026/pipeline.py', 'evaluation/wolala2026/adapters.py',
             'evaluation/wolala2026/run_pilot.py', 'evaluation/wolala2026/real_api.py',
             'backend_python/controlled_failure.py', 'backend_python/relevance.py',
             'evaluation/wolala2026/prompts/prompt_only_v1.txt', 'evaluation/wolala2026/prompts/cfaf_generator_v1.txt']


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(canonical(row) + '\n')


def append_jsonl(path, value):
    with Path(path).open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(canonical(value) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()


def prepare(out, revision):
    from datasets import load_dataset
    from huggingface_hub import HfApi
    if any((out / f).exists() for f in ('cases.jsonl', 'runtime_inputs.jsonl', 'dataset_provenance.json')):
        raise RuntimeError('Refusing to overwrite prepared dataset files; use a fresh --output-dir.')
    resolved = HfApi().dataset_info(DATASET, revision=revision or 'main').sha
    ds = load_dataset(DATASET, split='test', revision=resolved)
    cases = list(ds.select(range(10)))
    runtime = [{'perturbed_query': c['perturbed_query'], 'perturbed_context': c['perturbed_context']} for c in cases]
    for r in runtime:
        validate_runtime(r)
    write_jsonl(out / 'cases.jsonl', cases)
    write_jsonl(out / 'runtime_inputs.jsonl', runtime)
    tracked = git('ls-files').splitlines()
    original_hashes = {name: digest(REPO / name) for name in tracked if (REPO / name).is_file()}
    write_json(out / 'original_tracked_sha256.json', original_hashes)
    provenance = {
        'dataset': DATASET, 'revision': resolved, 'split': 'test', 'split_size': len(ds),
        'selected_indices': list(range(10)), 'original_ids': [c['id'] for c in cases],
        'selection': "load_dataset(dataset, split='test', revision=revision).select(range(10))",
        'dataset_fingerprint': ds._fingerprint,
        'checksum_serialization': "JSONL, sorted keys, ensure_ascii=True, separators=(',', ':'), UTF-8, LF after every record",
        'cases_sha256': digest(out / 'cases.jsonl'), 'runtime_inputs_sha256': digest(out / 'runtime_inputs.jsonl'),
        'repository_commit': git('rev-parse', 'HEAD'), 'experimental_branch': git('branch', '--show-current'),
        'protected_source_sha256': {name: digest(REPO / name) for name in PROTECTED},
        'prepared_at_utc': utc_now(), 'python': sys.version,
    }
    write_json(out / 'dataset_provenance.json', provenance)
    print(canonical({'selected': len(cases), 'revision': resolved, 'cases_sha256': provenance['cases_sha256']}))


class AuditedProvider(OpenAIProvider):
    """Reuse existing HTTP implementation; reserve attempts before network I/O."""
    def __init__(self, out):
        super().__init__(generator_model='gpt-4o-mini', timeout_seconds=45)
        self.out, self.attempts = out, 0
        self.index = self.mode = self.latest_metadata = self.error_status = None

    def _post_json(self, path, payload):
        if path != '/chat/completions':
            raise RuntimeError('Only primary generation calls are authorized by this runner.')
        if self.attempts >= 30:
            raise RuntimeError('Hard cap of 30 primary generation attempts reached.')
        self.attempts += 1
        self.latest_metadata = self.error_status = None
        request_no = self.attempts
        append_jsonl(self.out / 'api_requests.jsonl', {
            'attempt': request_no, 'index': self.index, 'mode_name': self.mode,
            'started_at_utc': utc_now(), 'endpoint': path, 'payload': payload,
            'payload_sha256': hashlib.sha256(canonical(payload).encode()).hexdigest(),
        })
        start = time.perf_counter()
        try:
            result = super()._post_json(path, payload)
        except Exception as exc:
            cause = exc.__cause__
            self.error_status = cause.code if isinstance(cause, urllib.error.HTTPError) else None
            append_jsonl(self.out / 'api_events.jsonl', {
                'attempt': request_no, 'index': self.index, 'mode_name': self.mode,
                'status': 'ERROR', 'http_status': self.error_status,
                'error': redact(str(exc)), 'latency_ms': (time.perf_counter() - start) * 1000,
            })
            raise
        choice = (result.get('choices') or [{}])[0]
        self.latest_metadata = {
            'model': result.get('model'), 'response_id': result.get('id'),
            'finish_reason': choice.get('finish_reason'), 'usage': result.get('usage'),
            'system_fingerprint': result.get('system_fingerprint'),
            'refusal': (choice.get('message') or {}).get('refusal'),
        }
        append_jsonl(self.out / 'api_events.jsonl', {
            'attempt': request_no, 'index': self.index, 'mode_name': self.mode,
            'status': 'SUCCESS', 'metadata': self.latest_metadata,
            'latency_ms': (time.perf_counter() - start) * 1000,
        })
        return result


def redact(value):
    key = os.getenv('OPENAI_API_KEY')
    return value.replace(key, '<OPENAI_API_KEY>') if key else value


def validate_ten_runtime(runtime):
    if len(runtime) != 10:
        raise ValueError('Exactly ten runtime records are required.')
    for record in runtime:
        validate_runtime(record)


def audit(out):
    runtime = read_jsonl(out / 'runtime_inputs.jsonl')
    validate_ten_runtime(runtime)
    audits = []
    for index, record in enumerate(runtime):
        case = adapt_runtime(record, index)
        snapshot = build_retrieval_snapshot(case)
        state = run_pipeline(case)
        assert_pipeline_invariants(state)
        assert snapshot['candidates'][0]['permitted_experimental_raw_text'] == record['perturbed_context']
        assert state.candidates[0].content == record['perturbed_context']
        audits.append({
            'index': index, 'runtime_input_sha256': hashlib.sha256(canonical(record).encode()).hexdigest(),
            'stage_sequence': state.internal_trace['stage_sequence'],
            'gate_prediction': state.mode_decision.mode.value, 'gate_reason_code': state.mode_decision.reason_code,
            'deterministic_response': state.final_response, 'all_invariants_passed': True, 'actual_api_calls': 0,
            'note': 'Local pipeline audit only. Fixture token/model counters are not real API measurements.',
            'pipeline_state': json.loads(state.to_json()),
        })
    write_jsonl(out / 'deterministic_audit.jsonl', audits)
    print(canonical({'deterministic_cases': len(audits), 'actual_api_calls': 0}))


def generate(out):
    # No cases.jsonl, dataset provenance, original IDs or scoring imports here.
    runtime = read_jsonl(out / 'runtime_inputs.jsonl')
    validate_ten_runtime(runtime)
    for name in ('generation_results.jsonl', 'generation_manifest.json', 'api_requests.jsonl', 'api_events.jsonl'):
        if (out / name).exists():
            raise RuntimeError('Refusing to overwrite/resume live execution artifacts; use a fresh output directory.')
    frozen = {p.name: digest(p) for p in sorted(HERE.glob('*.py'))}
    frozen['runtime_inputs.jsonl'] = digest(out / 'runtime_inputs.jsonl')
    write_json(out / 'prerun_protocol.json', {
        'frozen_at_utc': utc_now(), 'source_hashes': frozen, 'adapter': ADAPTER_VERSION,
        'indices': list(range(10)), 'modes': ALL_MODES, 'model': 'gpt-4o-mini',
        'temperature': 0, 'max_output_tokens': 160, 'repetitions': 1,
        'max_primary_generation_attempts': 30, 'max_retries': 0, 'embeddings': 0,
        'classifier_calls': 0, 'evidence_role': 'UNKNOWN', 'runtime_answer': 'absent', 'gold_answer': 'absent',
        'prediction_interpretation': 'strict JSON top_level_mode with nonempty string answer, identical for all systems; no contract repair',
        'refusal_reason_interpretation': 'Unique explicit original refusal code or specific lexical reason among the six documented categories; generic EVIDENTIAL or multiple matching reasons -> unmeasurable; see frozen scoring.py',
        'support_review': 'Post-generation manual claim-level review from query, perturbed context and actual response; no external world-knowledge verification; evidence and ambiguity concerns recorded.',
    })
    started = utc_now()
    provider = AuditedProvider(out) if os.getenv('OPENAI_API_KEY') else None
    blocker = None if provider else 'OPENAI_API_KEY is absent or empty.'
    rows = []
    for index, record in enumerate(runtime):
        case = adapt_runtime(record, index)
        snapshot = build_retrieval_snapshot(case)
        for mode in ALL_MODES:
            start = time.perf_counter()
            before = provider.attempts if provider else 0
            row = {'index': index, 'runtime_id': case['case_id'], 'mode_name': mode,
                   'repetition': 1, 'real_api': True, 'actual_api_attempts': 0,
                   'actual_api_usage': None, 'execution_status': 'NOT_EXECUTED',
                   'raw_model_output': '', 'public_response': None,
                   'question_sha256': hashlib.sha256(record['perturbed_query'].encode()).hexdigest(),
                   'context_sha256': hashlib.sha256(record['perturbed_context'].encode()).hexdigest()}
            if blocker:
                row['blocker'] = blocker
            else:
                provider.index, provider.mode = index, mode
                try:
                    result = adapter_for_mode(mode).run(case, snapshot, run_id='refusalbench-nq-first10-v1', repetition=1, provider=provider, max_output_tokens=160)
                    row.update(result)
                    row['execution_status'] = 'SUCCESS'
                    row['actual_api_usage'] = {'input_tokens': result['input_tokens'], 'output_tokens': result['output_tokens']}
                    row['provider_metadata'] = provider.latest_metadata
                except Exception as exc:
                    row['execution_status'] = 'ERROR'
                    row['error'] = redact(str(exc))
                    row['http_status'] = provider.error_status
                    if provider.error_status in {401, 403, 429} or isinstance(exc.__cause__, urllib.error.URLError):
                        blocker = row['error']
                row['actual_api_attempts'] = provider.attempts - before
            row['end_to_end_ms'] = (time.perf_counter() - start) * 1000
            append_jsonl(out / 'generation_results.jsonl', row)
            rows.append(row)
            print(canonical({'index': index, 'mode': mode, 'status': row['execution_status'], 'attempts_so_far': provider.attempts if provider else 0}), flush=True)
    write_json(out / 'generation_manifest.json', {
        'started_at_utc': started, 'finished_at_utc': utc_now(), 'python': sys.version,
        'platform': platform.platform(), 'model': 'gpt-4o-mini', 'temperature': 0,
        'max_output_tokens': 160, 'repetitions': 1, 'scheduled_system_cases': 30,
        'api_key_present': bool(os.getenv('OPENAI_API_KEY')), 'actual_generation_attempts': provider.attempts if provider else 0,
        'actual_embedding_calls': 0, 'actual_classifier_calls': 0, 'retries': 0,
        'successful_system_cases': sum(r['execution_status'] == 'SUCCESS' for r in rows),
        'blocker': blocker, 'repository_commit': git('rev-parse', 'HEAD'),
        'branch': git('branch', '--show-current'), 'source_sha256': frozen,
        'dependencies': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
    })


def score(out):
    # First command to join labels to generated results.
    from evaluation.refusalbench_pilot.scoring import score_one, summarize
    cases = read_jsonl(out / 'cases.jsonl')
    rows = read_jsonl(out / 'generation_results.jsonl')
    reviews_path = out / 'response_reviews.jsonl'
    reviews = {(r['index'], r['mode_name']): r for r in read_jsonl(reviews_path)} if reviews_path.exists() else {}
    if len(cases) != 10 or len(rows) != 30 or {(r['index'], r['mode_name']) for r in rows} != {(i, m) for i in range(10) for m in ALL_MODES}:
        raise ValueError('Scoring requires exactly 10 cases and 30 unique system-case results.')
    provenance = json.loads((out / 'dataset_provenance.json').read_text())
    if digest(out / 'cases.jsonl') != provenance['cases_sha256'] or digest(out / 'runtime_inputs.jsonl') != provenance['runtime_inputs_sha256']:
        raise ValueError('Prepared input checksums changed.')
    runtime = read_jsonl(out / 'runtime_inputs.jsonl')
    for index, case in enumerate(cases):
        if runtime[index] != {k: case[k] for k in ('perturbed_query', 'perturbed_context')}:
            raise ValueError('Runtime input differs from original selected record.')
    for row in rows:
        row['scoring'] = score_one(cases[row['index']], row, reviews.get((row['index'], row['mode_name'])))
    write_jsonl(out / 'results.jsonl', rows)
    summary = summarize(cases, rows)
    summary.update({'dataset_revision': provenance['revision'], 'repository_commit': provenance['repository_commit'], 'cases_sha256': provenance['cases_sha256']})
    original = json.loads((out / 'original_tracked_sha256.json').read_text())
    changed = [name for name, expected in original.items() if not (REPO / name).exists() or digest(REPO / name) != expected]
    summary['modified_original_tracked_files'] = changed
    if changed:
        raise RuntimeError('Original tracked files were modified: ' + ', '.join(changed))
    protocol = json.loads((out / 'prerun_protocol.json').read_text())
    source_changes = [name for name, value in protocol['source_hashes'].items() if digest((out if name == 'runtime_inputs.jsonl' else HERE) / name) != value]
    summary['post_generation_code_changes'] = source_changes
    if source_changes:
        raise RuntimeError('Pre-run frozen code changed: ' + ', '.join(source_changes))
    summary['actual_api_blocker'] = json.loads((out / 'generation_manifest.json').read_text())['blocker']
    write_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'audit', 'generate', 'score'))
    parser.add_argument('--output-dir', type=Path, default=HERE)
    parser.add_argument('--revision', help='Hugging Face commit SHA; main is resolved once if omitted')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = REPO / 'work' / 'refusalbench_cache'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_HOME', str(cache / 'hf'))
    os.environ.setdefault('HF_DATASETS_CACHE', str(cache / 'datasets'))
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    if args.command == 'prepare':
        prepare(out, args.revision)
    else:
        {'audit': audit, 'generate': generate, 'score': score}[args.command](out)


if __name__ == '__main__':
    main()
