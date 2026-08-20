# Human QA execution guide

Status: `PENDING_HUMAN_ASSIGNMENT`

Gábor must decide the MailEx licence/redistribution disposition, gold-QA owners,
primary and second MailEx annotators, agreement metric and acceptance threshold,
adjudicator, citation auditors, manual no-health signer and freeze authority.
The tools implement raw agreement and Cohen's kappa but choose no official
metric or threshold.

Annotators receive only the approved blinded package, an anonymized annotator
ID and the annotation guideline. Primary annotators fill their human label,
evidence/document/message references and notes. A distinct second annotator
fills the same fields for exactly 20% of assigned items. Machine suggestions
remain separate and never count as a human field. Annotators return the same CSV
schema without reordering IDs or exposing their identity in content fields.

Run assignment and required-field validation before distribution and again on
return. Agreement is computed only when every paired human label is complete.
Disagreements export with blank adjudicator, adjudicated label and reason;
import rejects incomplete or unknown items. Citation audit stays pending until
all selected rows have support, correct-page, missing/inaccessible and reviewer
fields. No-health sign-off stays pending until every corpus/artifact block has a
signer, decision and time. Gold QA stays pending until every row has a human
decision.

Statuses may move from pending to human-complete only after the corresponding
validator passes and the designated human accepts the file. This task creates
no assignment decision, label, agreement result, adjudication, citation score,
no-health sign-off or gold correction. Before freeze it remains prohibited to
use holdout gold in the runner, tune on holdout/frozen data, approve the MailEx
licence by inference, run a provider, cherry-pick E1 cases, or mark pending
manual work complete.
