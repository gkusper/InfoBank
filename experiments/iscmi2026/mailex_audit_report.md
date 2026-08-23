# MailEx Technical Audit for ISCMI 2026

## 1. Dataset Identification

Dataset: MailEx / Email Event and Argument Extraction.

Project URL: https://github.com/salokr/Email-Event-Extraction

Dataset URL: https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view

HuggingFace mirror inspected for metadata comparison: https://huggingface.co/datasets/salokr/MailEx

Input kind: `zip`

Input SHA-256: `dda3ce5da5ffc3452dd9e5a58cd69e19e68bd655eafe1deec48e87204f6c37b4`

## 2. Licence and Research-use Status

- Project README evidence: README.md Licensing Information states the dataset is distributed under CC BY-SA 4.0.
- HuggingFace dataset-card evidence: README.md metadata declares license: cc-by-4.0.
- Dataset-internal licence files observed: []
- Attribution required: True
- Share-alike status: Required under the project README CC BY-SA 4.0 claim; not required under the HuggingFace cc-by-4.0 metadata.
- Scope: The project README explicitly says the dataset is distributed under CC BY-SA 4.0; the HuggingFace dataset card license metadata applies to the dataset card/repository. No separate code LICENSE was found.

Licensing note: Exact public redistribution terms are ambiguous because project README says CC BY-SA 4.0 while HuggingFace metadata says cc-by-4.0 and no dataset-internal LICENSE file was observed.

For internal research auditing, both cited Creative Commons variants permit reuse with attribution. For public redistribution of derived materials, the exact CC BY versus CC BY-SA obligation should be resolved before release.

## 3. Actual Dataset Structure

Observed file counts:

- Total files in ZIP/object tree: 4754
- Split JSON files: {'train': 1200, 'dev': 150, 'test': 150}
- Full-data JSON files: 1500
- Raw thread files: 1506
- Extension counts: {'(none)': 1507, '.json': 3000, '.txt': 1}

The primary annotated split data lives under `data/train`, `data/dev`, and `data/test`. Each split file is a JSON document with `events` and `sentences` top-level keys. `data/raw_threads` contains concatenated raw-ish thread text files, many with trailing-dot filenames. `data/full_data` contains 1500 JSON files parallel to the split data in the downloaded ZIP.

The HuggingFace Git mirror was also inspected and currently exposes only 100 train JSON files while the Google Drive ZIP exposes 1200 train JSON files. The audit therefore treats the Google Drive ZIP as the complete dataset source for measured annotation statistics.

## 4. Message Structure

- Annotated turns/messages: 3936
- Nonempty annotated turns: 3609
- Empty or placeholder turns: 327
- Message identifier: No explicit per-message ID in split JSON; thread file and turn_N index can form a local ID.
- Thread identifier: Recoverable from JSON file name.
- Sender: Not in split JSON; partially recoverable from raw_threads FROM headers.
- Recipients: Not in split JSON; partially recoverable from raw_threads TO headers.
- CC/BCC: Rare/mostly absent in raw_threads; not in split JSON.
- Timestamp/date: Not in split JSON; only rare DATE-like raw headers observed.
- Subject: Not in split JSON; recoverable from raw_threads SUBJECT headers.
- Body: Tokenized body text is available in split JSON sentences.
- Quoted previous messages: No explicit quote structure in split JSON; raw_threads preserve concatenated history-like text.
- Ordering: Recoverable from turn_0, turn_1, ... order.
- Reply relationships: No Message-ID/In-Reply-To/References graph observed.

Raw header evidence:

- Raw segments: min 2, median 2.0, max 11
- Raw header field occurrences, top 20: {'SUBJECT': 3934, 'FROM': 3928, 'TO': 3920, 'HTTP': 53, 'FAX': 40, 'DATE': 29, 'PHONE': 24, 'AIRCRAFT': 18, 'TEL': 14, 'TIME': 11, 'EMAIL': 11, 'RATE': 11, 'O': 9, 'TELEPHONE': 8, 'TERM': 7, 'TRADERS': 6, 'HOME': 6, 'COMMENTS': 5, 'NOTE': 5, 'MARK': 5}
- Raw DATE values observed: 29
- Parsed DATE values: 15
- Malformed DATE values: 14

## 5. Thread Reconstruction

- Distinct annotated threads: 1500
- Split thread counts: {'train': 1200, 'dev': 150, 'test': 150}
- Thread length min/mean/median/max: 2 / 2.624 / 2.0 / 11
- P25/P75/P90: 2.0 / 3.0 / 4.0
- Single-message threads: 0
- Threads with at least 2 messages: 1500
- Threads with at least 3 messages: 612
- Threads with at least 4 messages: 206
- Threads with at least 5 messages: 79

MailEx supports a local sequence equivalent to `turn_0 -> turn_1 -> ...` within each JSON file. It does not expose a reliable absolute timestamp sequence or Message-ID/In-Reply-To graph in the annotated split JSON.

## 6. MailEx Annotation Model

Observed top-level annotation shape:

- `events[turn_N][event_type].labels`: BIO argument labels over the tokenized turn.
- `events[turn_N][event_type].triggers`: serialized trigger dictionaries with words and indices.
- `events[turn_N][event_type].extras`: meta-semantic strings such as deliver confirmation or amend action.

Annotated event instances excluding `O`: 8392

Event types:

| Event type | Instances | Event groups | Threads | Example trigger |
|---|---:|---:|---:|---|
| Amend_Action_Data | 3 | 3 | 3 | will sign on my behalf |
| Amend_Data | 193 | 153 | 129 | For this report please include |
| Amend_Meeting_Data | 55 | 53 | 42 | The party is back |
| Deliver_Action_Data | 3195 | 1604 | 1081 | quarantined |
| Deliver_Data | 1820 | 1262 | 943 | it was , Fairfield weather forecast |
| Deliver_Meeting_Data | 487 | 409 | 337 | are coming over for dinner |
| Request_Action | 1376 | 1048 | 774 | Let me know |
| Request_Action_Data | 233 | 212 | 188 | where we are with delivering |
| Request_Data | 721 | 602 | 491 | What did you send |
| Request_Meeting | 259 | 246 | 214 | would love for you to come |
| Request_Meeting_Data | 50 | 48 | 46 | let us know |

Top argument roles by span count:

- Action Description: 4895
- Action Members: 4097
- Data idString: 2635
- Data Value: 1562
- Meeting Members: 1235
- Action Date: 771
- Deliver members: 447
- Request members: 399
- Meeting Date: 391
- Meeting Agenda: 372
- Meeting Time: 242
- Meeting Name: 210
- Deliver Members: 209
- Meeting Location: 182
- Amend Members: 123
- Action Time: 118
- Request Members: 113
- Data Type: 38
- Request Date: 29
- Deliver Date: 26

Top meta-semantic extras:

- Deliver Confirmation : : 5191
- Query Items  : Data Value: 716
- Deliver Confirmation : Negative: 174
- Query Items  : Action Description: 157
- Amend Action : Update: 147
- Deliver Confirmation : Positive: 129
- Amend Action : Add: 55
- Query Items  : Action Members: 53
- Amend Action : : 36
- Query Items  : Meeting Date: 19
- Query Items  : Action Date: 14
- Amend Action : Delete: 13
- Query Items  : Meeting Members: 11
- Query Items  : Meeting Time: 10
- Deliver Confirmation : Unsure: 8
- Query Items  : Meeting Location: 7
- Query Items  : Action Time: 7
- Query Items  : : 5
- Query Items  : Meeting Agenda: 3
- Query Items  : Request Time: 1

Event dependencies and cross-message event relations are not explicitly annotated. Events can be associated with a specific thread file and `turn_N` email.

## 7. Quantitative Statistics

Annotation-based action-related thread counts:

```json
{
  "Amend_Action_Data": 3,
  "Deliver_Action_Data": 1081,
  "Request_Action": 774,
  "Request_Action_Data": 188
}
```

Deterministic lexical candidate counts by thread:

```json
{
  "cancel": 125,
  "commitment": 673,
  "completion": 650,
  "confirm": 321,
  "deadline": 512,
  "modify": 413,
  "reject": 216,
  "request": 1245
}
```

These lexical counts are transparent candidate indicators only. They are not ground truth labels.

## 8. Data Quality Issues

- duplicate_turn_text_hashes: 227
- empty_turns: 327
- missing_raw_thread_for_split_thread: 2
- threads_with_empty_turns: 282

Additional issues:

- Raw thread files: 1506 files but 1506 normalized raw IDs.
- Raw duplicate IDs: 0.
- Raw files not matched to split threads: 8.
- Windows-problematic trailing-dot raw filenames: 1276.
- HuggingFace mirror train split count differs from the Google Drive ZIP count.

## 9. Suitability for ISCMI 2026

Classification: **SUITABLE WITH ADDITIONAL MANUAL ANNOTATION**

MailEx provides ordered multi-message threads and explicit event/action annotations such as Request_Action and Deliver_Action_Data, so it can support a later manual pilot for action-item evolution. It does not provide final ISCMI transition labels, evidence roles, task-state labels, reliable timestamps, reply graphs, or explicit cross-message event dependencies.

The dataset is useful for a later manual pilot because it contains ordered email turns, action/request/delivery/amendment event types, trigger spans, argument spans, and meta-semantic extras. It is not sufficient by itself as final ISCMI ground truth because communication transitions, evidence roles, and task states are not MailEx labels.

## 10. Candidate Mapping to ISCMI Transitions

- CREATE: Request_Action, Request_Action_Data, Request_Meeting and request lexical indicators.
- CONFIRM: Deliver_Action_Data extras such as Deliver Confirmation : Positive plus confirm lexical indicators.
- MODIFY: Amend_* event types, Amend Action extras and modify lexical indicators.
- COMPLETE: Deliver_Action_Data/Deliver_Data and completion lexical indicators.
- CANCEL: Sparse Amend Action : Delete and cancel/delete lexical indicators; manual confirmation needed.
- REJECT: Deliver Confirmation : Negative and reject lexical indicators; sparse and ambiguous.

These mappings are feasibility notes only. No CREATE/CONFIRM/MODIFY/COMPLETE/CANCEL/REJECT labels were assigned.

## 11. Limitations

- Licence metadata is inconsistent across source locations.
- Split JSON lacks structured sender, recipient, date, CC/BCC, Message-ID, and reply-reference fields.
- Raw headers are partial and sparse for dates.
- Some turns are empty placeholders.
- Cross-message event dependencies are absent.
- Lexical candidate counts are heuristics, not labels.

## 12. Recommendation

**SUITABLE WITH ADDITIONAL MANUAL ANNOTATION**

MailEx is appropriate for a follow-up manual pilot shortlist and later carefully documented annotation work. It should not be treated as ready-made ISCMI transition/state ground truth, and public redistribution terms should be clarified before releasing derived examples or benchmark subsets.
