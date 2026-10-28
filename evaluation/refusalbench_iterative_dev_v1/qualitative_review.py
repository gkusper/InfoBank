"""Non-independent report-author review of significant already-exposed errors."""
from pathlib import Path
from .exposure import ROOT

NOTES={
'round_01':{
0:'Edition-specific wording adds an unsupported qualifier to a definition. Scope is unresolved and the analyzer also rejects granularity. The official FULL label is preserved; exact edition provenance is not established by the passage.',
3:'The band-member query combines unresolved general WHO typing with an insufficient explicit-list judgment; distributed names in the passage require relation/coreference interpretation. No label is rewritten.',
4:'The candidate identifies Matthew and Luke but required-support flags and unresolved WHERE typing reject fulfilment. This combines profiling and sufficiency inconsistency.',
5:'The control gives both independently named periodic-table composers while the official label calls the singular request ambiguous. This is an official failure to restrict; answering both names can be reasonable under a broader reading, but the first/unique qualifier still needs justification.',
6:'The query adds a release-year qualifier not matching the passage title. The official expected mode remains FULL. Refusal can reflect unsupported qualifiers, not only profiler failure; later qualified actor answers do not validate the false year.',
9:'The passage directly associates the actor and role; unresolved general WHO profiling is the sole gate blocker. This is a clear unnecessary refusal rather than missing evidence.',
12:'The passage gives vaccine availability in a decade. The assessor demands greater precision and treats the request as unresolved; exact-day precision was not explicitly asked for. Milestone interpretation and unnecessary abstention remain issues.',
13:'The control raw mode is CFAF but fulfilment_status FULL; uniform scoring correctly records ERROR rather than a valid refusal. The false-premise reason also needs independent semantic review.',
14:'The historical-influence query has a supported candidate but unresolved WHO typing blocks it. This is a clear general factual-coverage defect.',
16:'The query includes a discovery date absent from a passage about the tablets container. Gold FULL is preserved. The source cannot establish that added historical qualifier; the control also has a CFAF/FULL-status inconsistency.',
17:'The control output is structurally contradictory in mode/status. No valid prediction is credited, and it is not repaired for scoring.',
18:'The control output is structurally contradictory in mode/status. A refusal-shaped prose answer cannot be credited by ignoring the incompatible structured fields.',
19:'The compound yes/no plus authorship question lacks a recognized profile despite a substantive candidate. Multipart and BOOLEAN factual typing are general improvements, not a special answer rule.'},
'round_02':{
0:'A truncated passage names an electricity authority and plants but does not specify actual energy sources. Both systems refuse against an official FULL label; the label and required source/agency interpretation are questionable, not corrected.',
1:'The passage contains an original work and adaptation with the same title. Both systems select the original author without resolving the intended work. This is a query-reference/answer-relation error rather than an internal contradiction problem.',
6:'A telegraphic bowler-identity query receives an otherwise grounded candidate but remains UNRESOLVED. The later query-only fallback is designed for this class of nominal fragments, without seeing context or gold.',
7:'Two film titles have different filming locations. Listing locations for both does not resolve a singular this-film referent. Both systems return official false FULLs; the final version adds a referent-resolution property and uncertainty requirement.',
14:'A query uses an unsupported edition year for a role. The model incorrectly labels this NONFACTUAL rather than distinguish a factual core from an unsupported qualifier. The official FULL label remains unchanged.',
15:'A yes/no question about a fictional cultural figure can be factual historical-influence inquiry. UNRESOLVED profiling and NONFACTUAL labeling conflate subject matter with epistemic request type.'},
'round_03':{
5:'Oregon has multiple reinstatement dates/events in the passage. The model selects 1984 and marks referent resolution/complete fulfilment true despite the deictic request. The selected fact is present, but complete disambiguation is not established; official CFAF is unchanged.',
8:'The question asks for band members while adding an unsupported award presupposition. The assessor rejects both membership and award evidence and even marks the referent unresolved. Core members appear across the narrative; unsupported incidental qualifiers and list coverage remain difficult. Official FULL is preserved, not repaired.',
9:'The passage supplies two roles in the same show; the model chooses one and incorrectly marks complete coverage true. A cited true role does not establish complete fulfilment or remove alternative-role ambiguity. This is an official failure to restrict.'},
'paired_regression':{
0:'The final profile recognizes the definition question, but another granularity flag still blocks CFAF FULL while the control answers. The per-requirement complete flag and broader granularity flag are inconsistent. This shows that typing alone does not settle evidence assessment.',
5:'The final version returns the two named periodic-table composers. The official label requests refusal for ambiguity; the same ambiguity-versus-list interpretation issue remains. All labels and primary outcomes stay unchanged.',
6:'A qualified final answer names the actor and the series year supported by the passage, rather than repeating the unsupported query year. Correct official mode alone still does not prove every presupposition or detail has been resolved.',
8:'The model extrapolates a century-long national trend from a limited collection of states and events. A valid quotation does not establish representative historical coverage; this is an official granularity failure-to-restrict case.',
12:'The final assessor still requires an exact date where the question can accept decade-level availability. It then labels missing precision as an unresolved referent. This exposes semantic reason inconsistency despite the improved profile.',
16:'The purported discovery date is absent from the permitted text. Official FULL remains unchanged. Missing evidence and unsupported qualifiers are conflated with ambiguity/nonfactual status; a faithful restricted answer can disagree with the benchmark label.'}}

def write():
 for directory,notes in NOTES.items():
  path=ROOT/directory/'error_analysis.md'
  with path.open('a',encoding='utf-8') as f:
   f.write('\n## Contextual report-author review\n\nThese notes are post-run, unblinded agent judgments, not independent human gold or score corrections. Only already-selected, exposure-charged records were reviewed.\n')
   for i,note in sorted(notes.items()):f.write(f'\n- Case {i}: {note}\n')
 return NOTES
if __name__=='__main__':write()
