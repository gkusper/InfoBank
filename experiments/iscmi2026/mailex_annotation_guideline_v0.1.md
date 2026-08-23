# MailEx ISCMI 2026 Annotation Guideline v0.1

This guideline defines the manual research annotation model for the ISCMI 2026
MailEx pilot. It is for later human annotation only. MailEx event labels remain
the original source annotations and must not be treated as ISCMI ground truth.

No RAG implementation, automatic semantic annotation, evidence-role annotation,
or model-based labeling is part of this guideline.

## Unit of Analysis

Annotate ordered email threads. Read each thread chronologically as
`message 1`, `message 2`, and so on. A message may contain zero, one, or
multiple tasks/action items.

A task/action item is a requested, promised, assigned, scheduled, revised, or
closed unit of work that a person or group could plausibly perform or decide
about. General information, greetings, background facts, and quoted history are
not tasks unless they create, change, confirm, complete, cancel, or reject a
concrete action.

## Task Identity

Use local task IDs within each pilot thread:

- `T1`
- `T2`
- `T3`
- continue as needed.

Assign task IDs after reading the whole thread once.

Two mentions refer to the same task when they share the same practical goal,
actor/responsible party, and object of work, even if later messages add details,
clarify timing, or adjust scope.

A later mention is a modified task, not a new task, when it changes deadline,
assignee, scope, required output, or conditions while preserving the same core
goal.

Treat mentions as separate tasks when they require distinct work products,
different outcomes, independent responsible actors, or can be completed or
closed independently. A single email can create several task IDs.

Repeated requests or reminders normally keep the same task ID unless they add a
separate actionable requirement.

## Transition Labels

Use exactly one transition label for each state-changing task mention.

### `CREATE`

A task is introduced, requested, assigned, proposed for action, or newly
committed to. Use `CREATE` for the first actionable mention of a task, including
requests, promises, invitations requiring action, and assignments.

### `CONFIRM`

The message confirms, acknowledges, approves, or verifies an already existing
task or plan without showing that the required work has been performed.

Distinguish `CONFIRM` from `COMPLETE`: confirmation says the task/plan is
accepted, understood, approved, or still valid; completion says the work is done
or the requested output has been delivered.

### `MODIFY`

The message changes an existing task while preserving its identity. Examples
include new deadlines, changed scope, changed actor, revised document/version,
added constraints, removed subtasks, or corrected instructions.

Distinguish `MODIFY` from a new `CREATE`: if the later message preserves the
same practical goal and changes details, use `MODIFY`; if it introduces an
independent work item, assign a new task ID and use `CREATE`.

### `COMPLETE`

The message reports that the required work is done, sends the requested output,
or otherwise provides evidence that the task has been fulfilled. Partial
completion should be recorded as `COMPLETE` only for the completed portion; keep
the resulting state `OPEN` or `UNCERTAIN` if important requested work remains.

### `CANCEL`

The requester, owner, or conversation context withdraws, deletes, supersedes, or
makes the existing task no longer necessary.

Distinguish `CANCEL` from `REJECT`: `CANCEL` removes or withdraws the task;
`REJECT` refuses or declines the task while the request itself remains
recognizable.

### `REJECT`

The responsible actor or decision maker refuses, declines, cannot perform, or
negatively answers the task/request. Use this when the response blocks or denies
the requested action rather than completing it.

### `NONE`

The message contains no state-changing evidence for the task being annotated.
Use `NONE` for background, quoted material, greetings, unrelated information,
or repeated context that does not create, confirm, modify, complete, cancel, or
reject a task.

Distinguish `NONE` from uncertainty: `NONE` means the annotator judges that no
state change is present. If a possible state change exists but the evidence is
unclear, use the most defensible transition and lower confidence, or document
the ambiguity in notes.

## Task States

Use exactly one resulting state after each annotated transition.

### `OPEN`

The task appears active, pending, partially completed, awaiting response, or
otherwise not closed after the current evidence.

### `CLOSED`

The task appears completed, rejected, canceled, superseded, or otherwise no
longer requires action after the current evidence.

### `UNCERTAIN`

The available evidence is insufficient to decide whether the task is open or
closed. `UNCERTAIN` is an epistemic state, not a transition label.

Conversation ending without explicit closure should usually result in `OPEN` or
`UNCERTAIN`, depending on whether the remaining obligation is clear.

## Participants and Fields

Requester is the person or group asking for, assigning, proposing, or depending
on the action. Responsible actor is the person or group expected to perform or
decide the action. If either is missing, leave the field blank or write
`unknown` in notes according to the annotation sheet instructions.

Record deadlines when the thread explicitly states a date, time, relative
deadline, or scheduling constraint. Do not infer deadlines from general urgency
unless the wording makes a time constraint explicit.

Quoted previous messages should be used as context for understanding the thread,
but do not annotate quoted text as a new state change unless the current message
itself relies on or reactivates that content.

## Ambiguity and Confidence

Use confidence values exactly:

- `HIGH`: clear evidence, stable task identity, and little plausible ambiguity.
- `MEDIUM`: evidence is reasonable but some field, actor, scope, or state is
  uncertain.
- `LOW`: weak, indirect, contradictory, or incomplete evidence.

Contradictory evidence should be resolved chronologically where possible. If two
messages conflict and the later state is unclear, record the best transition,
set resulting state to `UNCERTAIN`, and explain the contradiction in notes.

For missing information, leave unavailable fields empty and document only
information supported by the thread. Do not guess names, deadlines, task
descriptions, or closure states.

## Special Cases

Partial completion can close one subtask while leaving the broader task open.
Use separate task IDs when the subparts are independently actionable; otherwise
use notes to explain the partial state.

Repeated requests and reminders usually receive `NONE` if they only restate an
existing task. Use `MODIFY` if the reminder changes deadline, scope, actor, or
required output.

Multiple requests in one message should receive separate task IDs when they are
independent. If they are steps of one practical goal, keep one task ID and
capture the combined description.

Conversation endings without explicit completion, cancellation, or rejection do
not automatically close a task.

## Recommended Human Workflow

1. Read the entire thread.
2. Identify tasks.
3. Assign `T1`, `T2`, etc.
4. Reread messages chronologically.
5. Identify state-changing evidence.
6. Assign transitions.
7. Record resulting states.
8. Produce task-level summary.
9. Record confidence and ambiguity.
