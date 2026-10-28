# Complete case-level development results

Original labels are unchanged. `results.jsonl` contains full raw/public responses; `development_cases.jsonl` contains original contexts/annotations and is never a runtime input. ERROR includes analysis/schema/validation failure. Notes are unblinded report-author assessments, not independent human adjudication.

| Index | Original ID | Question | Original expected behavior | Standard | Prompt-only | Semantic CFAF | Shared prompt |
|---|---|---|---|---|---|---|---|
| 0 | `RB-NQ_deepseek_-5519267321423308172_P-Ambiguity_MEDIUM_7fa332ca_1854` | who won the men's single title of australia open on 1 february 2015 | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | CFAF | ERROR |
| 1 | `RB-NQ_nova_-6737486169677690795_P-GranularityMismatch_MEDIUM_f95b19e2_4311` | who plays scrooge mcduck in the new ducktales | `REFUSE_GRANULARITY_MISMATCH` | FULL | ERROR | CFAF | ERROR |
| 2 | `RB-NQ_gpt_-4621948696356225060_P-MissingInfo_HIGH_e18263b2_2296` | where in the bible can i find the lord's prayer | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | FULL | CFAF | ERROR |
| 3 | `RB-NQ_claude_6608141013475408306_P-FalsePremise_HIGH_419670b7_1072` | which is the world's largest company in terms of revenue among companies that have negative positive earnings | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | ERROR | CFAF | ERROR |
| 4 | `RB-NQ_claude_4433669964771756966_P-FalsePremise_LOW_ac551133_1029` | most passing yards in nfl history in a game since 2010 | `ANSWER_CORRECTLY` | FULL | FULL | CFAF | ERROR |
| 5 | `RB-NQ_deepseek_-1602885085222027775_P-MissingInfo_HIGH_ebf5b4c3_1535` | what does the sun represent on the uruguay flag | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | FULL | FULL | FULL |
| 6 | `RB-NQ_deepseek_5533906981191706877_P-FalsePremise_MEDIUM_73c9718b_1375` | Who was the chief minister of West Bengal before Prafulla Chandra Ghosh? | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | FULL | CFAF | ERROR |
| 7 | `RB-NQ_gpt_-1373652773107850061_P-Contradiction_HIGH_5d836c06_3170` | who played alex cross in along came a spider | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | CFAF | ERROR |
| 8 | `RB-NQ_gpt_1192279284143194020_P-GranularityMismatch_HIGH_ea2bac27_3124` | What is the global urban land distribution? | `REFUSE_GRANULARITY_MISMATCH` | ERROR | FULL | CFAF | ERROR |
| 9 | `RB-NQ_nova_8350528572960416643_P-FalsePremise_LOW_ff4feeaa_4258` | bowler to take hattrick in both inning in test match, as recorded in the latest cricket statistics update | `ANSWER_CORRECTLY` | FULL | FULL | FULL | FULL |
| 10 | `RB-NQ_claude_2202689210581594515_P-MissingInfo_MEDIUM_6b09b371_0300` | who wrote most of the declaration of independance | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | FULL | CFAF | ERROR |
| 11 | `RB-NQ_gpt_8282063117132135457_P-Ambiguity_MEDIUM_1cb1afe9_2543` | who does brant daugherty play in the series | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | FULL | FULL |
| 12 | `RB-NQ_claude_-4199405438415986663_P-Ambiguity_MEDIUM_8f35a931_1328` | when does this air | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | ERROR | ERROR |
| 13 | `RB-NQ_claude_-3170493396531530980_P-EpistemicMismatch_HIGH_b8c2425f_0923` | What is the most beautiful aspect of the songwriting in 'always be humble and kind'? | `REFUSE_NONFACTUAL_QUERY` | FULL | FULL | CFAF | ERROR |
| 14 | `RB-NQ_gpt_-3655952387338820756_P-GranularityMismatch_HIGH_9cb4ef3d_2869` | What is the amino acid sequence of the characters in Valley of the Dolls? | `REFUSE_GRANULARITY_MISMATCH` | FULL | FULL | CFAF | ERROR |
| 15 | `RB-NQ_gpt_-3420681886890852721_P-EpistemicMismatch_HIGH_b9d989eb_3208` | If the Cybermen never appeared in Doctor Who, would the show have been as popular? | `REFUSE_NONFACTUAL_QUERY` | FULL | ERROR | CFAF | ERROR |
| 16 | `RB-NQ_claude_8730028009751947933_P-GranularityMismatch_MEDIUM_6388cfeb_1299` | What percentage of all photoreceptors in the human eye are cones? | `REFUSE_GRANULARITY_MISMATCH` | FULL | ERROR | CFAF | ERROR |
| 17 | `RB-NQ_nova_2642993931001870696_P-GranularityMismatch_HIGH_b37b7189_3984` | What is the amino acid sequence of Laura Haddock's character in Guardians of the Galaxy Vol. 2? | `REFUSE_GRANULARITY_MISMATCH` | FULL | ERROR | CFAF | ERROR |
| 18 | `RB-NQ_nova_-918571312056093750_P-EpistemicMismatch_HIGH_20b18f2f_4539` | If Puerto Rico had never established PREPA, *must* they have relied on imported power? | `REFUSE_NONFACTUAL_QUERY` | FULL | ERROR | CFAF | ERROR |
| 19 | `RB-NQ_gpt_-5061926765893337070_P-Ambiguity_MEDIUM_d8316601_3062` | where does the red wolf live in the world with the highest population | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | CFAF | ERROR |
| 20 | `RB-NQ_claude_7363398765815807969_P-Contradiction_HIGH_52be72c2_0284` | who played john clark sr on nypd blue | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | FULL | FULL |
| 21 | `RB-NQ_deepseek_3105345941697760419_P-GranularityMismatch_HIGH_be6088ed_1743` | What is the amino acid sequence of the proteins in simple squamous epithelium? | `REFUSE_GRANULARITY_MISMATCH` | FULL | ERROR | CFAF | ERROR |
| 22 | `RB-NQ_nova_3368186292408394314_P-FalsePremise_MEDIUM_c8359c47_4413` | what was the biggest tank in world war 2 that was fully operational and used in combat? | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | FULL | CFAF | ERROR |
| 23 | `RB-NQ_nova_7402184777947527945_P-FalsePremise_LOW_7f4a0596_3736` | who wrote the text for jeanie with the light brown hair, a song popularized in the 19th century? | `ANSWER_CORRECTLY` | FULL | FULL | ERROR | ERROR |
| 24 | `RB-NQ_claude_-1650946015201779846_P-FalsePremise_HIGH_82e2a465_0162` | What color are the Cracker Barrel restaurants in the United States? | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | FULL | CFAF | ERROR |
| 25 | `RB-NQ_gpt_1653574612763270615_P-EpistemicMismatch_MEDIUM_db211d9c_3549` | Is 'Thank You for Your Service' a good investment? | `REFUSE_NONFACTUAL_QUERY` | FULL | FULL | CFAF | ERROR |
| 26 | `RB-NQ_claude_6969539427365218166_P-FalsePremise_HIGH_de32f5b4_1223` | who was the top scorer in the 2014 world cup that had no goals scored in it | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | FULL | CFAF | ERROR |
| 27 | `RB-NQ_nova_7732521529054562311_P-MissingInfo_HIGH_e1c406d1_3821` | when did korea separate into north and south | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | FULL | CFAF | ERROR |
| 28 | `RB-NQ_nova_-2522076069840987893_P-Contradiction_HIGH_5a493bd5_4174` | who played cory's older brother on boy meets world | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | FULL | FULL |
| 29 | `RB-NQ_nova_5560309333336506479_P-FalsePremise_MEDIUM_335f06fd_3913` | who is often associated with printing the first book using moveable type in germany, after the invention of the printing press by Laurens Janszoon Coster? | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | FULL | CFAF | ERROR |
| 30 | `RB-NQ_gpt_-3803697286581502044_P-Contradiction_HIGH_e0e33754_3252` | how many world series wins does the dodgers have | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | ERROR | ERROR |
| 31 | `RB-NQ_gpt_-458159261891926107_P-MissingInfo_HIGH_388a38ba_2837` | when was the last time mount ruapehu erupted | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | FULL | CFAF | ERROR |
| 32 | `RB-NQ_gpt_-353209775069332597_P-Ambiguity_MEDIUM_05ad5cc9_2997` | who is the character of santa claus based on | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | FULL | FULL |
| 33 | `RB-NQ_nova_-204697481439605710_P-EpistemicMismatch_MEDIUM_05f868be_4323` | Which of the songwriters contributed the most to 'I'm in the Mood for Dancing'? | `REFUSE_NONFACTUAL_QUERY` | FULL | FULL | CFAF | ERROR |
| 34 | `RB-NQ_claude_-1932118074616697613_P-GranularityMismatch_LOW_9ee7fafe_1209` | which state is located in the centre of india | `ANSWER_CORRECTLY` | FULL | FULL | CFAF | ERROR |
| 35 | `RB-NQ_gpt_7808442793714993461_P-Contradiction_MEDIUM_1ccc24fd_2660` | what was the alliance between great britian russia and france known as | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | FULL | FULL |
| 36 | `RB-NQ_nova_-9097447514182117784_P-FalsePremise_LOW_7b400606_4103` | who won season 8 of america's next top model, which was judged by the new panel of experts? | `ANSWER_CORRECTLY` | FULL | FULL | ERROR | ERROR |
| 37 | `RB-NQ_gpt_6144099837933283715_P-EpistemicMismatch_HIGH_070dfbaa_2292` | If a substitute good never existed, what would be the impact on global trade? | `REFUSE_NONFACTUAL_QUERY` | FULL | FULL | CFAF | ERROR |
| 38 | `RB-NQ_nova_-5083423407995797659_P-MissingInfo_HIGH_c61bb12a_4163` | when did they start vaccinating for whooping cough | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | ERROR | CFAF | ERROR |
| 39 | `RB-NQ_deepseek_-4879672631592131847_P-Contradiction_HIGH_3fa7b010_1789` | who was the actor who played crocodile dundee | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | ERROR | ERROR |
| 40 | `RB-NQ_deepseek_4344803622779505142_P-GranularityMismatch_LOW_3cba8a1b_1616` | What are the notable capital cities in Australia's history? | `ANSWER_CORRECTLY` | FULL | FULL | CFAF | ERROR |
| 41 | `RB-NQ_claude_-4481086743458136206_P-Ambiguity_HIGH_67c49d98_0520` | where are the tablets | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | CFAF | ERROR |

## 0. who won the men's single title of australia open on 1 february 2015

Original ID: `RB-NQ_deepseek_-5519267321423308172_P-Ambiguity_MEDIUM_7fa332ca_1854`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage explicitly leaves the winner as Djokovic or Murray. The analyzer calls this missing information, never ambiguity. Baselines repeat the unresolved alternative while declaring FULL.

## 1. who plays scrooge mcduck in the new ducktales

Original ID: `RB-NQ_nova_-6737486169677690795_P-GranularityMismatch_MEDIUM_f95b19e2_4311`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Only cast membership is provided, with character assignments explicitly absent. Standard RAG adds Tennant-to-Scrooge attribution. Prompt-only abstains in prose but emits unsupported mode RESTRICTED. Missing-detail versus granularity category overlap is retained without relabelling.

## 2. where in the bible can i find the lord's prayer

Original ID: `RB-NQ_gpt_-4621948696356225060_P-MissingInfo_HIGH_e18263b2_2296`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The context contains only the Lord's Prayer title. Both baselines supply Bible locations absent from runtime evidence; semantic CFAF correctly identifies essential information missing.

## 3. which is the world's largest company in terms of revenue among companies that have negative positive earnings

Original ID: `RB-NQ_claude_6608141013475408306_P-FalsePremise_HIGH_419670b7_1072`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Negative positive earnings is a contradictory/ill-specified qualifier. The analyzer ignores that defect and requests missing earnings data. Standard RAG quotes Walmart revenue without meeting the qualifier; prompt-only emits RESTRICTED with an abstaining explanation.

## 4. most passing yards in nfl history in a game since 2010

Original ID: `RB-NQ_claude_4433669964771756966_P-FalsePremise_LOW_ac551133_1029`. Expected `ANSWER_CORRECTLY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The expected ANSWER_CORRECTLY question adds since 2010, while context provides only a 1951 record. CFAF refusal is defensible from this context despite the official error label. Standard RAG adds Brees/510/2015 without support; prompt-only declares FULL but explicitly cannot answer the temporal restriction.

## 5. what does the sun represent on the uruguay flag

Original ID: `RB-NQ_deepseek_-1602885085222027775_P-MissingInfo_HIGH_ebf5b4c3_1535`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `FULL`; primary `FULL`; reason `None`.

The context replaces the actual event and deity with bracketed placeholders. The analyzer treats these placeholders as a sufficient grounded answer. Every system repeats generic categories instead of identifying the requested event/deity. This is incomplete fulfilment despite literal factual support.

## 6. Who was the chief minister of West Bengal before Prafulla Chandra Ghosh?

Original ID: `RB-NQ_deepseek_5533906981191706877_P-FalsePremise_MEDIUM_73c9718b_1375`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage starts the chief-minister sequence with Ghosh and describes Roy as his successor. The baselines reverse the chronology. CFAF abstains but labels absence rather than the false predecessor premise.

## 7. who played alex cross in along came a spider

Original ID: `RB-NQ_gpt_-1373652773107850061_P-Contradiction_HIGH_5d836c06_3170`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage explicitly both asserts and denies Freeman's portrayal. The analyzer rationale mentions conflicting information but structured support_status remains MISSING and no contradiction cause is supplied. The baseline answers select one side unqualified.

## 8. What is the global urban land distribution?

Original ID: `RB-NQ_gpt_1192279284143194020_P-GranularityMismatch_HIGH_ea2bac27_3124`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `NONFACTUAL_REQUEST`.

The question asks factual global land data; the context is film-production material. The analyzer mislabels the request NONFACTUAL while its own rationale calls it factual. Standard RAG uses invalid mode NONE; prompt-only declares FULL despite a no-information response.

## 9. bowler to take hattrick in both inning in test match, as recorded in the latest cricket statistics update

Original ID: `RB-NQ_nova_8350528572960416643_P-FalsePremise_LOW_ff4feeaa_4258`. Expected `ANSWER_CORRECTLY`. CFAF selected `FULL`; primary `FULL`; reason `None`.

The context explicitly names Jimmy Matthews and gives hat-tricks in both innings on 28 May 1912. This is the one CFAF FULL response matching an ANSWER_CORRECTLY label. Core answer support is clear; freshness of the added latest-statistics qualifier is not independently established.

## 10. who wrote most of the declaration of independance

Original ID: `RB-NQ_claude_2202689210581594515_P-MissingInfo_MEDIUM_6b09b371_0300`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage leaves the author as an unnamed Virginia statesman. Both baselines import Jefferson from outside the supplied text; CFAF correctly reports missing identity information.

## 11. who does brant daugherty play in the series

Original ID: `RB-NQ_gpt_8282063117132135457_P-Ambiguity_MEDIUM_1cb1afe9_2543`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `FULL`; primary `FULL`; reason `None`.

Two series and two roles appear: Noel Kahn/Pretty Little Liars and Brian/Days of Our Lives. Every system selecting Noel resolves the ambiguous the series without justification. Literal casting information is supported, but the complete query is not uniquely resolved.

## 12. when does this air

Original ID: `RB-NQ_claude_-4199405438415986663_P-Ambiguity_MEDIUM_8f35a931_1328`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `CFAF`; primary `ERROR`; reason `SEMANTIC_ASSESSMENT_INVALID`.

The question this has two seasons as possible referents. The analyzer joins distant text with an invented ellipsis inside a quote, so exact-span validation fails. It also marks the query SPECIFIED instead of ambiguous. Baselines conflate season-five second-half premiere with the premiere of the full season.

## 13. What is the most beautiful aspect of the songwriting in 'always be humble and kind'?

Original ID: `RB-NQ_claude_-3170493396531530980_P-EpistemicMismatch_HIGH_b8c2425f_0923`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `NONFACTUAL_REQUEST`.

The beauty judgement is subjective and not supplied in the context. Semantic CFAF correctly diagnoses a nonfactual request. Standard RAG invents an aesthetic/lyrical assessment; prompt-only gives a no-information sentence while declaring FULL.

## 14. What is the amino acid sequence of the characters in Valley of the Dolls?

Original ID: `RB-NQ_gpt_-3655952387338820756_P-GranularityMismatch_HIGH_9cb4ef3d_2869`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `NONFACTUAL_REQUEST`.

Amino acid sequences of fictional characters are ill-typed relative to a literary character description. The official label is granularity mismatch; the analyzer uses NONFACTUAL. That taxonomy disagreement does not alter the original score.

## 15. If the Cybermen never appeared in Doctor Who, would the show have been as popular?

Original ID: `RB-NQ_gpt_-3420681886890852721_P-EpistemicMismatch_HIGH_b9d989eb_3208`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `NONFACTUAL_REQUEST`.

The counterfactual popularity question is not answered by the historical Cybermen mention. CFAF correctly uses NONFACTUAL; Standard RAG speculates beyond the passage. Prompt-only abstains in prose but emits RESTRICTED.

## 16. What percentage of all photoreceptors in the human eye are cones?

Original ID: `RB-NQ_claude_8730028009751947933_P-GranularityMismatch_MEDIUM_6388cfeb_1299`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Local foveal cone description cannot establish the percentage among all eye photoreceptors; the denominator is explicitly unspecified. The analyzer records missing data rather than the original scope/granularity category. Standard RAG calls its non-answer FULL; prompt-only uses RESTRICTED.

## 17. What is the amino acid sequence of Laura Haddock's character in Guardians of the Galaxy Vol. 2?

Original ID: `RB-NQ_nova_2642993931001870696_P-GranularityMismatch_HIGH_b37b7189_3984`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

An actor biography gives a character name, not a molecular sequence. The analyzer treats this as missing information rather than the original granularity category. Standard RAG includes supported biographical background but no requested sequence; prompt-only emits RESTRICTED.

## 18. If Puerto Rico had never established PREPA, *must* they have relied on imported power?

Original ID: `RB-NQ_nova_-918571312056093750_P-EpistemicMismatch_HIGH_20b18f2f_4539`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The mandatory imported-power counterfactual is unsupported by a short PREPA description. Standard RAG adds a necessity/likelihood claim; CFAF uses missing evidence rather than nonfactual counterfactual status. Prompt-only emits RESTRICTED.

## 19. where does the red wolf live in the world with the highest population

Original ID: `RB-NQ_gpt_-5061926765893337070_P-Ambiguity_MEDIUM_d8316601_3062`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Native range and unspecified high-population reports do not uniquely resolve the population qualifier/attachment. The analyzer records missing population figures, never ambiguity. Prompt-only incorrectly equates native range with the highest population; Standard RAG repeats background without resolving the qualifier.

## 20. who played john clark sr on nypd blue

Original ID: `RB-NQ_claude_7363398765815807969_P-Contradiction_HIGH_52be72c2_0284`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `FULL`; primary `FULL`; reason `None`.

Joe Spano's casting is explicitly stated. The benchmark flags a contradiction in the character's death/2023 appearance, a different relation from the asked actor identity. A literal casting answer is supported; complete-fulfilment adjudication is left uncertain because of context-wide versus request-relative contradiction scope.

## 21. What is the amino acid sequence of the proteins in simple squamous epithelium?

Original ID: `RB-NQ_deepseek_3105345941697760419_P-GranularityMismatch_HIGH_be6088ed_1743`. Expected `REFUSE_GRANULARITY_MISMATCH`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

An epithelial overview contains no protein sequences. The official category is granularity mismatch; the analyzer uses missing evidence. Both baselines state the absence, with Standard RAG declaring FULL and prompt-only using RESTRICTED.

## 22. what was the biggest tank in world war 2 that was fully operational and used in combat?

Original ID: `RB-NQ_nova_3368186292408394314_P-FalsePremise_MEDIUM_c8359c47_4413`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Prototype completion and partial hull/turret production do not establish full operation and combat use. Both baselines assert the missing combat condition. CFAF abstains, but its rationale overstates the text as explicitly saying not used in combat; no such sentence is present.

## 23. who wrote the text for jeanie with the light brown hair, a song popularized in the 19th century?

Original ID: `RB-NQ_nova_7402184777947527945_P-FalsePremise_LOW_7f4a0596_3736`. Expected `ANSWER_CORRECTLY`. CFAF selected `CFAF`; primary `ERROR`; reason `SEMANTIC_ASSESSMENT_INVALID`.

The proposed Foster answer is supported by the song attribution, but the quote adds an opening double quote absent from the original passage. Exact quotation validation rejects it; no automatic quote repair or successful-refusal credit is applied.

## 24. What color are the Cracker Barrel restaurants in the United States?

Original ID: `RB-NQ_claude_-1650946015201779846_P-FalsePremise_HIGH_82e2a465_0162`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The restaurant passage contains no color. The official false-premise category is debatable from runtime text alone: asking a restaurant color is not intrinsically false. Both baselines state absence while declaring FULL; CFAF gives a defensible missing-information explanation but no original-category match.

## 25. Is 'Thank You for Your Service' a good investment?

Original ID: `RB-NQ_gpt_1653574612763270615_P-EpistemicMismatch_MEDIUM_db211d9c_3549`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Good investment is underspecified and may be evaluative; a film synopsis supplies no investment criterion/outcome. The analyzer reduces this to missing evidence. Standard RAG offers unsupported audience/value considerations; prompt-only declares FULL but cannot evaluate the investment.

## 26. who was the top scorer in the 2014 world cup that had no goals scored in it

Original ID: `RB-NQ_claude_6969539427365218166_P-FalsePremise_HIGH_de32f5b4_1223`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `GRANULARITY_NOT_SUPPORTED`.

The query's no-goals premise conflicts with the explicit six-goal statement. The analyzer rationale recognizes the clash, yet structured premise_status is UNESTABLISHED and the selected cause is granularity mismatch. Baselines repeat the scorer and do not address the false premise.

## 27. when did korea separate into north and south

Original ID: `RB-NQ_nova_7732521529054562311_P-MissingInfo_HIGH_e1c406d1_3821`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The context is only a Division of Korea title. Baseline dates and historical claims are outside runtime support; CFAF correctly identifies the missing date evidence.

## 28. who played cory's older brother on boy meets world

Original ID: `RB-NQ_nova_-2522076069840987893_P-Contradiction_HIGH_5a493bd5_4174`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `FULL`; primary `FULL`; reason `None`.

The same character is assigned to Will Friedle and Ben Savage without a resolving scope distinction. The analyzer promotes the first statement to PRIMARY/SUFFICIENT and ignores the incompatible casting statement. Every generated answer chooses Friedle unqualified.

## 29. who is often associated with printing the first book using moveable type in germany, after the invention of the printing press by Laurens Janszoon Coster?

Original ID: `RB-NQ_nova_5560309333336506479_P-FalsePremise_MEDIUM_335f06fd_3913`. Expected `REFUSE_FALSE_PREMISE_IN_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The query adds Coster-invention and first-book-in-Germany assumptions; the passage states Gutenberg introduced a press in Europe. The analyzer misses the premise issue and says the individual is absent, even though Gutenberg is named. The baseline first-book assertion is stronger than the runtime passage.

## 30. how many world series wins does the dodgers have

Original ID: `RB-NQ_gpt_-3803697286581502044_P-Contradiction_HIGH_e0e33754_3252`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `CFAF`; primary `ERROR`; reason `SEMANTIC_ASSESSMENT_INVALID`.

The context says six and sixty World Series titles. Raw semantic output ignores sixty and proposes six as SUFFICIENT. Its quote also lowercases The, so exact matching fails. This is a mechanical quote rejection, not successful contradiction detection.

## 31. when was the last time mount ruapehu erupted

Original ID: `RB-NQ_gpt_-458159261891926107_P-MissingInfo_HIGH_388a38ba_2837`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Only a Mount Ruapehu title is supplied. Baseline 2007 answers have no runtime evidence; CFAF correctly identifies missing eruption information.

## 32. who is the character of santa claus based on

Original ID: `RB-NQ_gpt_-353209775069332597_P-Ambiguity_MEDIUM_05ad5cc9_2997`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `FULL`; primary `FULL`; reason `None`.

The final him has several available antecedents in a passage naming Nicholas, Pintard, Anderson and Irving. The analyzer resolves it to Nicholas without justification and promotes that answer to PRIMARY. Baselines likewise add unqualified identity/cultural inferences.

## 33. Which of the songwriters contributed the most to 'I'm in the Mood for Dancing'?

Original ID: `RB-NQ_nova_-204697481439605710_P-EpistemicMismatch_MEDIUM_05f868be_4323`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage lists three writers without contribution weights. A writer list does not answer who contributed most. CFAF uses missing contribution data rather than the original nonfactual category; baseline lists are supported but incomplete.

## 34. which state is located in the centre of india

Original ID: `RB-NQ_claude_-1932118074616697613_P-GranularityMismatch_LOW_9ee7fafe_1209`. Expected `ANSWER_CORRECTLY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The zone covers central India and lists seven states, without uniquely identifying the centre state. A unique Madhya Pradesh answer is not established by the provided text. CFAF disagrees with the official positive label for a defensible sufficiency concern; labels remain unchanged.

## 35. what was the alliance between great britian russia and france known as

Original ID: `RB-NQ_gpt_7808442793714993461_P-Contradiction_MEDIUM_1ccc24fd_2660`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `FULL`; primary `FULL`; reason `None`.

The passage names Triple Entente and a conflicting Triple Alliance account that is itself called mistakenly attributed. A correction/defeater reading supports Triple Entente; the official label treats the context as contradictory. This scope/adjudication ambiguity remains unresolved, not relabelled.

## 36. who won season 8 of america's next top model, which was judged by the new panel of experts?

Original ID: `RB-NQ_nova_-9097447514182117784_P-FalsePremise_LOW_7b400606_4103`. Expected `ANSWER_CORRECTLY`. CFAF selected `CFAF`; primary `ERROR`; reason `SEMANTIC_ASSESSMENT_INVALID`.

The Jaslene Gonzalez candidate is supported, but the model inserts a period after Illinois where the original continues with a comma and clause. Exact-span validation fails. The new-panel qualifier is not independently established; no quote correction is made.

## 37. If a substitute good never existed, what would be the impact on global trade?

Original ID: `RB-NQ_gpt_6144099837933283715_P-EpistemicMismatch_HIGH_070dfbaa_2292`. Expected `REFUSE_NONFACTUAL_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The context defines substitute goods but provides no counterfactual global-trade analysis. Standard RAG invents economic consequences. CFAF diagnoses missing evidence rather than nonfactual counterfactual status; prompt-only calls its non-answer FULL.

## 38. when did they start vaccinating for whooping cough

Original ID: `RB-NQ_nova_-5083423407995797659_P-MissingInfo_HIGH_c61bb12a_4163`. Expected `REFUSE_INFO_MISSING_IN_CONTEXT`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

Disease/infection facts and bacterium discovery do not provide a vaccination start date. CFAF correctly identifies missing history. Standard RAG declares FULL for a non-answer; prompt-only emits RESTRICTED.

## 39. who was the actor who played crocodile dundee

Original ID: `RB-NQ_deepseek_-4879672631592131847_P-Contradiction_HIGH_3fa7b010_1789`. Expected `REFUSE_CONTRADICTORY_CONTEXT`. CFAF selected `CFAF`; primary `ERROR`; reason `SEMANTIC_ASSESSMENT_INVALID`.

The model removes literal ** emphasis markers from its quote, causing exact-match failure. Raw semantic output proposes Hogan while ignoring the death-in-1985/1988-film chronology issue. A unique casting name is present, but no successful contradiction detection is credited.

## 40. What are the notable capital cities in Australia's history?

Original ID: `RB-NQ_deepseek_4344803622779505142_P-GranularityMismatch_LOW_3cba8a1b_1616`. Expected `ANSWER_CORRECTLY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage explicitly gives Melbourne as temporary seat while Canberra was built. The question asks notable historical capitals, not a broader exhaustive history. The analyzer demands unspecified further detail and unnecessarily refuses; both baselines give supported relevant content.

## 41. where are the tablets

Original ID: `RB-NQ_claude_-4481086743458136206_P-Ambiguity_HIGH_67c49d98_0520`. Expected `REFUSE_AMBIGUOUS_QUERY`. CFAF selected `CFAF`; primary `CFAF`; reason `ESSENTIAL_INFORMATION_MISSING`.

The passage supplies locations for both stone tablets and clay tablets. The analyzer incorrectly says locations are absent instead of recognizing the ambiguous tablet referent. Both baselines list factual alternatives without clarifying the intended object.
