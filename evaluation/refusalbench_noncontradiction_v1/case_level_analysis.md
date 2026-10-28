# Case-level RefusalBench filtered pilot analysis

All indices below are zero-based. Official labels remain unchanged. Post-run agent review is unblinded and non-independent; it never changes primary accuracy or turns questionable labels into errors/fixes. No extra judge API calls were made.

| Index | Official behavior | CFAF prediction / correct | Control prediction / correct | Explanation / grounding review |
|---:|---|---|---|---|
| 0 | REFUSE_NONFACTUAL_QUERY | CFAF / True | CFAF / True | Nonfactual best-experience judgment has no criteria or opinions in the passage. Both refusals are defensible. CFAF gives a generic unresolved-target explanation instead of the subjective cause; control describes the missing evaluation. Control declares CFAF with fulfilment_status FULL. |
| 1 | ANSWER_CORRECTLY | CFAF / False | FULL / True | Official ANSWER permits bridging from a named cast member to a particular role. The passage names David Tennant but does not attach him to Scrooge. CFAF is wrong under the official label, blocked by unresolved scope and an UNESTABLISHED premise despite SUFFICIENT support. Control matches the official label but the actor-to-role link is not established by this passage alone. |
| 2 | REFUSE_GRANULARITY_MISMATCH | CFAF / True | CFAF / True | The CO2 average request is resolved as AGGREGATE_AVERAGE, but the passage is about Vikings release dates. Both correctly restrict. Public explanations identify missing relevance rather than the official granularity category; this is not a global average inferable from local data in the supplied text. |
| 3 | ANSWER_CORRECTLY | CFAF / False | FULL / True | Matthew and Luke are explicitly identified. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker, so this is a clear unnecessary refusal caused by query profiling. Control answers the two gospels directly and completely. |
| 4 | REFUSE_NONFACTUAL_QUERY | CFAF / True | CFAF / True | The hypothetical cultural impact is not established by historical Sinterklaas facts. Both restrict. The semantic analyzer and CFAF explanation collapse counterfactual/nonfactual status into generic missing evidence; control explains why the hypothetical impact is unavailable. |
| 5 | REFUSE_INFO_MISSING_IN_CONTEXT | CFAF / True | FULL / False | The passage replaces the winner name with an unnamed top-seeded player. The analyzer nevertheless marks support SUFFICIENT and proposes that same placeholder as an answer to who. CFAF restricts because scope is unresolved, not because the missing identity was correctly detected. Control copies the supported description as FULL but leaves the requested identity unanswered. |
| 6 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | The passage distributes Dylan/Harrison/Petty/Lynne/Orbison across a recording narrative. Both refusals are official errors, with unresolved scope and a semantic demand for an explicit member list. Control then provides all five full names explicitly based on general knowledge, violating the supplied-context boundary and undermining its CFAF declaration. The passage contains the surnames, but does not establish all expanded names. |
| 7 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | A cultural-centre membership list does not explicitly designate one state as geographically central. Official ANSWER preserves Madhya Pradesh/Chhattisgarh from earlier answer annotations; both refusals remain official errors. The analyzer missing-support judgment is defensible for the actual passage. Control adds that Madhya Pradesh is often considered central, an assertion absent from the passage. |
| 8 | ANSWER_CORRECTLY | CFAF / False | FULL / True | The passage directly attaches Paul Hogan to Mick Dundee. The sole CFAF blocker is REQUEST_SCOPE_UNRESOLVED. Control gives a supported complete FULL answer. This is a clear profiling failure, not missing evidence. |
| 9 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | The actual query requests a specific example; the passage only defines the general term substitute good. Official ANSWER reasoning treats the genus term as a valid species/example answer. Both refusals are official errors, but their missing-example judgment is defensible. No new example is invented to improve the score. |
| 10 | REFUSE_FALSE_PREMISE_IN_QUERY | CFAF / True | CFAF / True | The married-bachelor premise is logically incompatible with the ordinary meaning of bachelor. Both correctly restrict, but the analyzer and public explanations treat it as an unrecorded relationship rather than identify the false premise. This is a query-premise issue retained by the exact filter, not an internal passage-contradiction experiment. |
| 11 | REFUSE_GRANULARITY_MISMATCH | CFAF / True | CFAF / True | One 1966 appearance cannot establish a whole-decade trend. Both correctly restrict; control explains that specific coverage gap. The inherited lexical reason recognizer does not recognize this paraphrase as the granularity category, so its automated unknown is not proof the prose is wrong. |
| 12 | ANSWER_CORRECTLY | CFAF / False | FULL / True | Lori McKenna is explicitly named as writer. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker. Control provides a supported complete answer. This is the third clear sole-profiler unnecessary refusal. |
| 13 | REFUSE_FALSE_PREMISE_IN_QUERY | CFAF / True | CFAF / True | The passage attributes movable-type press introduction to Gutenberg but says nothing about printing a second book. Both correctly restrict under the official false-premise label. Missing evidence does not by itself establish that the second-book premise is false; the official explanation also refers to a first-book statement absent from the perturbed passage. |
| 14 | REFUSE_AMBIGUOUS_QUERY | CFAF / True | CFAF / True | Two different named songs make this song unresolved. Both correctly restrict; control gives both songwriter alternatives and explicitly states ambiguity, the only recognized correct specific refusal category. Its CFAF plus fulfilment_status FULL is internally inconsistent even though its cautious prose can be appropriate. |
| 15 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | The passage gives 1940s availability and 1920s experimental vaccine development, which are different milestones rather than necessarily conflicting facts. Both refusals are official errors. The analyzer demands a specific vaccination start date; a qualified availability answer could satisfy the intended benchmark reading, while the first-vaccination interpretation remains uncertain. |
| 16 | REFUSE_INFO_MISSING_IN_CONTEXT | CFAF / True | CFAF / True | Both city names are replaced by placeholders. Both correctly restrict rather than supply an identity from world knowledge. Control explicitly says the first city is not specified; the lexical category recognizer misses that missing-information paraphrase. CFAF remains generic. |
| 17 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | The passage names the Ark as the described container of the tablets. Both refusals are official errors because the analyzer adds a current geographical-location requirement not explicit in the query. Container versus current-location readings create legitimate interpretive uncertainty; an answer qualified to the biblical description was possible. |
| 18 | REFUSE_AMBIGUOUS_QUERY | CFAF / True | FULL / False | The passage directly attaches Joe Spano to John Clark Sr and adds a different actor with the same printed name in another role. Official REFUSE_AMBIGUOUS is retained. CFAF matches it because scope is unresolved although the assessment is SUFFICIENT; control FULL is an official failure to restrict but is textually supported under a name-only interpretation. Unique-person disambiguation could require more evidence. |
| 19 | ANSWER_CORRECTLY | CFAF / False | CFAF / False | A factory foothold in 1611 and rights in 1612 do not establish when political control of India began. Both refusals are official errors under ANSWER, but the missing-control-date judgment is faithful to the actual passage. Control also declares CFAF with fulfilment_status FULL. No external historical date is supplied. |

## Case 00

Original ID: `RB-NQ_nova_1192279284143194020_P-EpistemicMismatch_MEDIUM_e793e512_4239`; source group `1192279284143194020`.

Question: Which location provided the best filming experience for the cast and crew of Diary of a Wimpy Kid: Dog Days?

Official behavior: `REFUSE_NONFACTUAL_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

No evidence indicates which location provided the best filming experience for the cast and crew of "Diary of a Wimpy Kid: Dog Days." The document lists several filming locations but does not evaluate their experiences.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

Nonfactual best-experience judgment has no criteria or opinions in the passage. Both refusals are defensible. CFAF gives a generic unresolved-target explanation instead of the subjective cause; control describes the missing evaluation. Control declares CFAF with fulfilment_status FULL.

Attribution: query interpretation, incorrect CFAF reason, output semantic consistency.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 01

Original ID: `RB-NQ_nova_-6737486169677690795_P-GranularityMismatch_LOW_adc746b2_4310`; source group `-6737486169677690795`.

Question: who plays scrooge mcduck in the new ducktales

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** FULL, official mode correct.

David Tennant plays Scrooge McDuck in the new DuckTales.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

Official ANSWER permits bridging from a named cast member to a particular role. The passage names David Tennant but does not attach him to Scrooge. CFAF is wrong under the official label, blocked by unresolved scope and an UNESTABLISHED premise despite SUFFICIENT support. Control matches the official label but the actor-to-role link is not established by this passage alone.

Attribution: query interpretation, evidence sufficiency, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 02

Original ID: `RB-NQ_nova_-4199405438415986663_P-GranularityMismatch_HIGH_d4204ca4_4555`; source group `-4199405438415986663`.

Question: What is the global average CO₂ concentration?

Official behavior: `REFUSE_GRANULARITY_MISMATCH` → `CFAF`.

Profile: `RESOLVED`; requirements: AGGREGATE_AVERAGE.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:AGGREGATE_AVERAGE.

**semantic_cfaf:** CFAF, official mode correct.

The currently usable evidence does not support the requested content.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

No relevant information about global average CO₂ concentration is provided in the document.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The CO2 average request is resolved as AGGREGATE_AVERAGE, but the passage is about Vikings release dates. Both correctly restrict. Public explanations identify missing relevance rather than the official granularity category; this is not a global average inferable from local data in the supplied text.

Attribution: evidence sufficiency, incorrect CFAF reason, benchmark category breadth.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 03

Original ID: `RB-NQ_deepseek_-4621948696356225060_P-GranularityMismatch_LOW_40ebb780_1403`; source group `-4621948696356225060`.

Question: Which notable books in the Bible contain the Lord's Prayer?

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** FULL, official mode correct.

The Lord's Prayer is found in the Gospel of Matthew and the Gospel of Luke.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

Matthew and Luke are explicitly identified. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker, so this is a clear unnecessary refusal caused by query profiling. Control answers the two gospels directly and completely.

Attribution: query interpretation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 04

Original ID: `RB-NQ_gpt_-353209775069332597_P-EpistemicMismatch_HIGH_7f6fcc89_3008`; source group `-353209775069332597`.

Question: If the character of Santa Claus was never based on any historical figure, what would be the cultural impact today?

Official behavior: `REFUSE_NONFACTUAL_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The query regarding the cultural impact of Santa Claus if he were never based on a historical figure cannot be answered due to a lack of relevant evidence. The available document discusses the origins of Sinterklaas and its evolution into Santa Claus but does not provide insights into the hypothetical scenario posed in the query.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The hypothetical cultural impact is not established by historical Sinterklaas facts. Both restrict. The semantic analyzer and CFAF explanation collapse counterfactual/nonfactual status into generic missing evidence; control explains why the hypothetical impact is unavailable.

Attribution: query interpretation, incorrect CFAF reason.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 05

Original ID: `RB-NQ_deepseek_-5519267321423308172_P-MissingInfo_MEDIUM_d21a3af8_1859`; source group `-5519267321423308172`.

Question: who won the men's single title of australia open on 1 february 2015

Official behavior: `REFUSE_INFO_MISSING_IN_CONTEXT` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** FULL, official mode incorrect.

The top-seeded player won the Men's Singles title at the 2015 Australian Open.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The passage replaces the winner name with an unnamed top-seeded player. The analyzer nevertheless marks support SUFFICIENT and proposes that same placeholder as an answer to who. CFAF restricts because scope is unresolved, not because the missing identity was correctly detected. Control copies the supported description as FULL but leaves the requested identity unanswered.

Attribution: evidence sufficiency, incomplete FULL response, query interpretation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 06

Original ID: `RB-NQ_claude_-2382302837416986186_P-FalsePremise_LOW_93d6c7cd_0487`; source group `-2382302837416986186`.

Question: who are the artists in the traveling wilburys supergroup

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document does not explicitly list the members of the Traveling Wilburys supergroup. However, based on general knowledge, the members are Bob Dylan, George Harrison, Jeff Lynne, Tom Petty, and Roy Orbison.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

The passage distributes Dylan/Harrison/Petty/Lynne/Orbison across a recording narrative. Both refusals are official errors, with unresolved scope and a semantic demand for an explicit member list. Control then provides all five full names explicitly based on general knowledge, violating the supplied-context boundary and undermining its CFAF declaration. The passage contains the surnames, but does not establish all expanded names.

Attribution: query interpretation, evidence sufficiency, unsupported added answer, contract/prose disagreement.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 07

Original ID: `RB-NQ_deepseek_-1932118074616697613_P-MissingInfo_LOW_1c51d1cc_2138`; source group `-1932118074616697613`.

Question: which state is located in the centre of india

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `RESOLVED`; requirements: DOCUMENT_CONTENT.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:DOCUMENT_CONTENT.

**semantic_cfaf:** CFAF, official mode incorrect.

The currently usable evidence does not support the requested content.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document does not specify which state is located in the center of India. It lists several states, including Madhya Pradesh, which is often considered geographically central, but does not confirm this explicitly.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

A cultural-centre membership list does not explicitly designate one state as geographically central. Official ANSWER preserves Madhya Pradesh/Chhattisgarh from earlier answer annotations; both refusals remain official errors. The analyzer missing-support judgment is defensible for the actual passage. Control adds that Madhya Pradesh is often considered central, an assertion absent from the passage.

Attribution: evidence sufficiency, benchmark ambiguity, unsupported added answer.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 08

Original ID: `RB-NQ_deepseek_-4879672631592131847_P-MissingInfo_LOW_b5eda8fb_1790`; source group `-4879672631592131847`.

Question: who was the actor who played crocodile dundee

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** FULL, official mode correct.

Paul Hogan played Crocodile Dundee.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The passage directly attaches Paul Hogan to Mick Dundee. The sole CFAF blocker is REQUEST_SCOPE_UNRESOLVED. Control gives a supported complete FULL answer. This is a clear profiling failure, not missing evidence.

Attribution: query interpretation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 09

Original ID: `RB-NQ_deepseek_6144099837933283715_P-GranularityMismatch_LOW_1b0bebf4_1391`; source group `6144099837933283715`.

Question: a specific example of a good that can be used in place of another good

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document defines a substitute good but does not provide a specific example. Therefore, I cannot fulfill the request for a specific example of a good that can be used in place of another good.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

The actual query requests a specific example; the passage only defines the general term substitute good. Official ANSWER reasoning treats the genus term as a valid species/example answer. Both refusals are official errors, but their missing-example judgment is defensible. No new example is invented to improve the score.

Attribution: query interpretation, evidence sufficiency, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 10

Original ID: `RB-NQ_gpt_-2522076069840987893_P-FalsePremise_HIGH_b3aa19dc_3044`; source group `-2522076069840987893`.

Question: What is the name of Cory's married bachelor brother on Boy Meets World?

Official behavior: `REFUSE_FALSE_PREMISE_IN_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The document provides information about Eric Randall Matthews, who is Cory's brother, but it does not confirm him as a married bachelor. Therefore, the specific name of Cory's married bachelor brother is not available.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The married-bachelor premise is logically incompatible with the ordinary meaning of bachelor. Both correctly restrict, but the analyzer and public explanations treat it as an unrecorded relationship rather than identify the false premise. This is a query-premise issue retained by the exact filter, not an internal passage-contradiction experiment.

Attribution: query interpretation, incorrect CFAF reason.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 11

Original ID: `RB-NQ_deepseek_-3420681886890852721_P-GranularityMismatch_MEDIUM_c8a666b7_1994`; source group `-3420681886890852721`.

Question: Describe the trend of Cybermen appearances in Doctor Who throughout the 1960s

Official behavior: `REFUSE_GRANULARITY_MISMATCH` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The document mentions Cybermen in the context of the 1966 BBC "Doctor Who" serial "The Tenth Planet" but does not provide information on the trend of their appearances throughout the 1960s. Therefore, a detailed trend analysis of Cybermen appearances in Doctor Who during that decade is not available.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

One 1966 appearance cannot establish a whole-decade trend. Both correctly restrict; control explains that specific coverage gap. The inherited lexical reason recognizer does not recognize this paraphrase as the granularity category, so its automated unknown is not proof the prose is wrong.

Attribution: evidence sufficiency, reason recognizer limitation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 12

Original ID: `RB-NQ_claude_-3170493396531530980_P-MissingInfo_LOW_ab95e851_0913`; source group `-3170493396531530980`.

Question: who wrote the song always be humble and kind

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** FULL, official mode correct.

The song 'Humble and Kind' was written by Lori McKenna.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

Lori McKenna is explicitly named as writer. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker. Control provides a supported complete answer. This is the third clear sole-profiler unnecessary refusal.

Attribution: query interpretation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 13

Original ID: `RB-NQ_deepseek_5560309333336506479_P-FalsePremise_MEDIUM_27936d3e_1669`; source group `5560309333336506479`.

Question: who is often associated with printing the second book using moveable type in germany

Official behavior: `REFUSE_FALSE_PREMISE_IN_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The document does not provide information about the individual associated with printing the second book using movable type in Germany. Therefore, I cannot confirm the identity of that person.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The passage attributes movable-type press introduction to Gutenberg but says nothing about printing a second book. Both correctly restrict under the official false-premise label. Missing evidence does not by itself establish that the second-book premise is false; the official explanation also refers to a first-book statement absent from the perturbed passage.

Attribution: query interpretation, incorrect CFAF reason, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 14

Original ID: `RB-NQ_claude_4925057086725798331_P-Ambiguity_MEDIUM_4bc92460_1144`; source group `4925057086725798331`.

Question: who wrote this song

Official behavior: `REFUSE_AMBIGUOUS_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The song "Yakety Yak" was written by Jerry Leiber and Mike Stoller, while "Don't Talk Back" was written by Bobby Darin. The query did not specify which song was being referred to, leading to ambiguity.

Fine refusal category recognized by frozen lexical scorer: `REFUSE_AMBIGUOUS_QUERY`. Context-specific explanation; see case note; lexical category recognition is separate.

Two different named songs make this song unresolved. Both correctly restrict; control gives both songwriter alternatives and explicitly states ambiguity, the only recognized correct specific refusal category. Its CFAF plus fulfilment_status FULL is internally inconsistent even though its cautious prose can be appropriate.

Attribution: query interpretation, output semantic consistency.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 15

Original ID: `RB-NQ_nova_-5083423407995797659_P-EpistemicMismatch_LOW_156e5d84_4169`; source group `-5083423407995797659`.

Question: when did they start vaccinating for whooping cough

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document states that the pertussis vaccine became available in the 1940s, but it does not provide a specific start date for vaccination against whooping cough.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

The passage gives 1940s availability and 1920s experimental vaccine development, which are different milestones rather than necessarily conflicting facts. Both refusals are official errors. The analyzer demands a specific vaccination start date; a qualified availability answer could satisfy the intended benchmark reading, while the first-vaccination interpretation remains uncertain.

Attribution: query interpretation, evidence sufficiency, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 16

Original ID: `RB-NQ_claude_4344803622779505142_P-MissingInfo_HIGH_a6ab7141_0382`; source group `4344803622779505142`.

Question: what was the first capital city of australia

Official behavior: `REFUSE_INFO_MISSING_IN_CONTEXT` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** CFAF, official mode correct.

The document does not specify the first capital city of Australia, and therefore I cannot provide that information.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

Both city names are replaced by placeholders. Both correctly restrict rather than supply an identity from world knowledge. Control explicitly says the first city is not specified; the lexical category recognizer misses that missing-information paraphrase. CFAF remains generic.

Attribution: evidence sufficiency, reason recognizer limitation.

Benchmark interpretation concern: False. All original annotations are retained.

## Case 17

Original ID: `RB-NQ_gpt_-4481086743458136206_P-MissingInfo_LOW_683700c1_2755`; source group `-4481086743458136206`.

Question: where is the tablet of the ten commandments

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document states that the tablets of the Ten Commandments are contained within the Ark of the Covenant. However, it does not specify their current location, leading to a partial support for the query.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

The passage names the Ark as the described container of the tablets. Both refusals are official errors because the analyzer adds a current geographical-location requirement not explicit in the query. Container versus current-location readings create legitimate interpretive uncertainty; an answer qualified to the biblical description was possible.

Attribution: query interpretation, evidence sufficiency, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 18

Original ID: `RB-NQ_nova_7363398765815807969_P-Ambiguity_HIGH_6ef40407_3773`; source group `7363398765815807969`.

Question: who played john clark sr on nypd blue

Official behavior: `REFUSE_AMBIGUOUS_QUERY` → `CFAF`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: REQUEST_SCOPE_UNRESOLVED.

**semantic_cfaf:** CFAF, official mode correct.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation.

**shared_control:** FULL, official mode incorrect.

John Clark Sr. was played by Joe Spano.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate.

The passage directly attaches Joe Spano to John Clark Sr and adds a different actor with the same printed name in another role. Official REFUSE_AMBIGUOUS is retained. CFAF matches it because scope is unresolved although the assessment is SUFFICIENT; control FULL is an official failure to restrict but is textually supported under a name-only interpretation. Unique-person disambiguation could require more evidence.

Attribution: query interpretation, benchmark ambiguity.

Benchmark interpretation concern: True. All original annotations are retained.

## Case 19

Original ID: `RB-NQ_gpt_-1176280233636154422_P-MissingInfo_LOW_819fadb5_2423`; source group `-1176280233636154422`.

Question: when did the east india company take control of india

Official behavior: `ANSWER_CORRECTLY` → `FULL`.

Profile: `UNRESOLVED`; requirements: UNRESOLVED.

Gate issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED.

**semantic_cfaf:** CFAF, official mode incorrect.

The requested target or information cannot be resolved from the permitted evidence.

Fine refusal category recognized by frozen lexical scorer: `None`. Generic/non-specific unresolved-target explanation. Unnecessary refusal under unchanged official label.

**shared_control:** CFAF, official mode incorrect.

The document does not provide a specific date for when the East India Company took control of India. It mentions the establishment of a factory in 1611 and the grant of rights in 1612, but does not indicate when control was established.

Fine refusal category recognized by frozen lexical scorer: `None`. Context-specific explanation; see case note; lexical category recognition is separate. Unnecessary refusal under unchanged official label.

A factory foothold in 1611 and rights in 1612 do not establish when political control of India began. Both refusals are official errors under ANSWER, but the missing-control-date judgment is faithful to the actual passage. Control also declares CFAF with fulfilment_status FULL. No external historical date is supplied.

Attribution: query interpretation, evidence sufficiency, benchmark ambiguity, output semantic consistency.

Benchmark interpretation concern: True. All original annotations are retained.
