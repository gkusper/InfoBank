# Source Provenance

Source repository:

https://github.com/salokr/Email-Event-Extraction

Observed source commit and downloaded archive checksum are recorded in
`source_manifest.json`.

Dataset download URL:

https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view

Observed extracted structure:

```text
data/
  train/
  dev/
  test/
  raw_threads/
  full_data/
```

Observed split counts:

- train: 1200 threads
- dev: 150 threads
- test: 150 threads

Transformation summary:

- D6 uses selected MailEx `Request_Action` candidates with useful action
  descriptions.
- D7 is generated deterministically from the D6 action topic with
  `deterministic_topic_trace_v1`.
- D8 uses later MailEx `Deliver_Action_Data` material when a conservative
  lexical closure signal is present.
- D8_NONCLOSING uses later MailEx action-related material with progress or
  future-commitment wording and no closure signal.
- Runtime inputs and hidden gold labels are separated between `cases.jsonl` and
  `gold.jsonl`.
- E-mail addresses, phone-like strings, participant fields, and selected
  person-name tokens are pseudonymized in redistributed excerpts.
- Raw MailEx data and archives are excluded from Git under `data/external/`.
