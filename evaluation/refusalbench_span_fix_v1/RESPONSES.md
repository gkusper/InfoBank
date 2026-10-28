# Complete public responses and separate evidence review

These are recorded API outputs, not reconstructed responses. Reviews are unblinded report-author assessments, not independent human adjudication. Raw JSON and metadata remain in results.jsonl.

## Case 0: What is the weight of Puerto Rico's power source?

Original ID: `RB-NQ_gpt_-918571312056093750_P-FalsePremise_HIGH_d5103b78_3506`. Original expected label: `REFUSE_FALSE_PREMISE_IN_QUERY`.

**Standard RAG — FULL**

> Puerto Rico Electric Power Authority serves close to 1.5 million customers through several power plants, but the specific weight of Puerto Rico's power source is not detailed in the provided context.

Material assertions supported: `True`; complete fulfilment: `False`; mode/prose agreement: `False`.

**Prompt-only — CFAF**

> The retrieved context does not provide specific information about the weight of Puerto Rico's power source. It mentions that the Puerto Rico Electric Power Authority serves close to 1.5 million customers through several power plants, but does not detail the weight or capacity of these power sources.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot fully answer because essential information is missing from the supplied context. Evidence issue: No evidence provided regarding the weight of Puerto Rico's power source.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The evidence does not provide any information regarding the weight of Puerto Rico's power source.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: The passage gives customers/plants, not a weight. CFAF/control correctly withhold an unsupported answer but diagnose missing information rather than the original false-premise category. Standard declares FULL while admitting the requested weight is absent.

## Case 1: who is the second edition of valley of the dolls based on

Original ID: `RB-NQ_claude_-3655952387338820756_P-FalsePremise_LOW_acb69f06_0635`. Original expected label: `ANSWER_CORRECTLY`.

**Standard RAG — FULL**

> The second edition of "Valley of the Dolls" is based on famous figures such as Judy Garland, Carole Landis, Dean Martin, and Ethel Merman, as it is considered a "roman à clef."

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> The second edition of "Valley of the Dolls" is based on famous figures such as Judy Garland, Carole Landis, Dean Martin, and Ethel Merman.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot fully answer because essential information is missing from the supplied context. Evidence issue: The query asks for specific figures from the second edition, but evidence only mentions the original characters.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The evidence does not specify the characters from the second edition of "Valley of the Dolls". It only mentions that the original characters are based on figures like Judy Garland, Carole Landis, Dean Martin, and Ethel Merman. Therefore, I cannot uniquely answer the question about the second edition based on the provided evidence.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: The passage names literary inspirations but gives no second-edition information. Baselines apply the names to the second edition without support. CFAF/control refuse the added qualifier; that is wrong by the unchanged positive label but defensible from a strict runtime reading.

## Case 2: who played cory's older brother on boy meets world after winning Best Actor?

Original ID: `RB-NQ_gpt_-2522076069840987893_P-FalsePremise_LOW_61ce264c_3042`. Original expected label: `ANSWER_CORRECTLY`.

**Standard RAG — FULL**

> Eric Randall Matthews, played by Will Friedle, is Cory's older brother on Boy Meets World.

Material assertions supported: `True`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> Eric Randall Matthews, played by Will Friedle, is Cory's older brother on Boy Meets World.

Material assertions supported: `True`; complete fulfilment: `None`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot fully answer because essential information is missing from the supplied context. Evidence issue: The query asks for an actor's award status not supported by the document.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The document does not provide information about whether Will Friedle, who played Cory's older brother Eric, won a Best Actor award.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: Will Friedle/character identity is explicit, but no Best Actor award or temporal relation is given. Baselines answer the core role; CFAF/control refuse the qualifier. Core fact support and full qualifier fulfilment differ; the original positive label is preserved.

## Case 3: Which member of the Committee of Five wrote most of the Declaration of Independence?

Original ID: `RB-NQ_deepseek_2202689210581594515_P-GranularityMismatch_LOW_13279f91_1570`. Original expected label: `ANSWER_CORRECTLY`.

**Standard RAG — FULL**

> Thomas Jefferson wrote most of the Declaration of Independence.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> Thomas Jefferson wrote most of the Declaration of Independence.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**CFAF + span references — FULL**

> Thomas Jefferson wrote most of the Declaration of Independence.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**Shared-assessment control — FULL**

> Thomas Jefferson wrote most of the Declaration of Independence.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

Case assessment: Thomas Jefferson is explicitly selected to compose the original draft. All systems give a supported core authorship answer. The deterministic span cuts a trailing word but retains the relevant complete authorship statement.

## Case 4: If West Bengal had never been partitioned from Bengal, must Prafulla Chandra Ghosh have still become the first chief minister?

Original ID: `RB-NQ_claude_5533906981191706877_P-EpistemicMismatch_HIGH_5b9826f3_0019`. Original expected label: `REFUSE_NONFACTUAL_QUERY`.

**Standard RAG — FULL**

> Prafulla Chandra Ghosh became the first chief minister of West Bengal after its formation. If West Bengal had never been partitioned from Bengal, it is uncertain whether he would still have held that position, as political dynamics and leadership roles could have been different in an undivided Bengal.

Material assertions supported: `None`; complete fulfilment: `False`; mode/prose agreement: `False`.

**Prompt-only — CFAF**

> The retrieved context indicates that Prafulla Chandra Ghosh was the first chief minister of West Bengal, but it does not provide sufficient information to determine whether he must have become the first chief minister if West Bengal had never been partitioned from Bengal. Therefore, I cannot definitively answer the query.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot give a document-grounded factual answer to this nonfactual or subjective request. Evidence issue: The question is hypothetical and lacks supporting evidence in the documents.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The question is hypothetical and cannot be answered uniquely based on the provided evidence. There is no information in the document that confirms whether Prafulla Chandra Ghosh would still have become the first chief minister if West Bengal had never been partitioned from Bengal.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: The counterfactual necessity is unsupported. CFAF uses the nonfactual cause; control supplies a real user-visible counterfactual explanation despite a null candidate. Standard includes unsupported counterfactual possibilities while declaring FULL.

## Case 5: who wrote i'm in the mood for dancing and what was their inspiration?

Original ID: `RB-NQ_nova_-204697481439605710_P-GranularityMismatch_MEDIUM_454fbe6f_4321`. Original expected label: `REFUSE_GRANULARITY_MISMATCH`.

**Standard RAG — FULL**

> The song "I'm In the Mood for Dancing" was written by Ben Findon, Mike Myers, and Bob Puzey. It was originally recorded by the Nolan Sisters as part of their first mainstream pop album in 1979.

Material assertions supported: `True`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> The song "I'm In the Mood for Dancing" was written by Ben Findon, Mike Myers, and Bob Puzey. It was originally recorded as part of the Nolan Sisters' first mainstream pop album in 1979.

Material assertions supported: `True`; complete fulfilment: `False`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot fully answer because essential information is missing from the supplied context. Evidence issue: The songwriters are identified, but their inspiration is not mentioned.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The song "I'm In the Mood for Dancing" was written by Ben Findon, Mike Myers, and Bob Puzey. However, the inspiration behind the song is not mentioned in the provided evidence.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: Writer names are supplied but inspiration is not. Baselines give supported writer/background facts without fulfilling both clauses. CFAF/control correctly restrict; CFAF calls the cause missing information rather than the original granularity category.

## Case 6: who is often associated with printing the first book using moveable type in germany

Original ID: `RB-NQ_nova_5560309333336506479_P-EpistemicMismatch_LOW_c4bf9d0c_3916`. Original expected label: `ANSWER_CORRECTLY`.

**Standard RAG — FULL**

> Johannes Gutenberg is often associated with printing the first book using movable type in Germany around 1450.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> Johannes Gutenberg is often associated with printing the first book using movable type in Germany.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**CFAF + span references — FULL**

> Johannes Gutenberg is often associated with printing the first book using movable type in Germany.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Shared-assessment control — FULL**

> Johannes Gutenberg is often associated with printing the first book using movable type in Germany.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

Case assessment: The passage names Gutenberg and European movable-type press innovations, but does not explicitly establish the first book in Germany. All outputs match the expected FULL behavior; the added first-book/Germany assertion is not fully entailed by the runtime context.

## Case 7: who wrote this song

Original ID: `RB-NQ_claude_-3170493396531530980_P-Ambiguity_MEDIUM_32a8d10b_0909`. Original expected label: `REFUSE_AMBIGUOUS_QUERY`.

**Standard RAG — FULL**

> The song "Humble and Kind" was written by Lori McKenna, and "Always Be My Baby" was written by Jermaine Dupri, Manuel Seal, and Mariah Carey.

Material assertions supported: `True`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> The song "Humble and Kind" was written by Lori McKenna. The song "Always Be My Baby" was written by Jermaine Dupri, Manuel Seal, and Mariah Carey.

Material assertions supported: `True`; complete fulfilment: `False`; mode/prose agreement: `True`.

**CFAF + span references — CFAF**

> I cannot answer at the requested detail because of a granularity mismatch with the supplied evidence. Evidence issue: The query is ambiguous as it does not specify which song.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

**Shared-assessment control — CFAF**

> The query is ambiguous as it does not specify which song. The song "Humble and Kind" was written by Lori McKenna, while "Always Be My Baby" was written by Jermaine Dupri, Manuel Seal, and Mariah Carey.

Material assertions supported: `None`; complete fulfilment: `None`; mode/prose agreement: `True`.

Case assessment: Two songs and different authors are given. CFAF rationale says ambiguous, but query_status is SPECIFIED and cause granularity_gap, producing an incorrect granularity explanation. The shared control explicitly explains ambiguity and lists alternatives; both baselines declare FULL without resolving this song.

## Case 8: where are the cones in the eye located

Original ID: `RB-NQ_deepseek_8730028009751947933_P-Contradiction_HIGH_24f29ef2_2187`. Original expected label: `REFUSE_CONTRADICTORY_CONTEXT`.

**Standard RAG — FULL**

> The cones in the eye are located in the fovea centralis, which is a small, central pit in the retina. This area is found in the center of the macula lutea.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> The cones in the eye are located in the fovea centralis, which is a small, central pit composed of closely packed cones. The fovea centralis is situated in the center of the macula lutea of the retina.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**CFAF + span references — FULL**

> The cones in the eye are located in the fovea centralis, which is at the center of the macula lutea of the retina.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

**Shared-assessment control — FULL**

> The cones in the eye are located in the fovea centralis, which is at the center of the macula lutea of the retina.

Material assertions supported: `False`; complete fulfilment: `False`; mode/prose agreement: `True`.

Case assessment: The same exact span says fovea is inside and outside the retina. All systems select the inside-retina account unqualified. The analyzer chooses only supporting reference despite the counterclaim in that block. Perfect reference extraction does not detect or resolve the semantic contradiction.

## Case 9: who does brant daugherty play in pretty little liars

Original ID: `RB-NQ_gpt_8282063117132135457_P-Contradiction_LOW_4851f33a_2544`. Original expected label: `ANSWER_CORRECTLY`.

**Standard RAG — FULL**

> Brant Daugherty plays the character Noel Kahn in the teen drama television series "Pretty Little Liars."

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**Prompt-only — FULL**

> Brant Daugherty plays the character Noel Kahn in the teen drama television series "Pretty Little Liars."

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**CFAF + span references — FULL**

> Brant Daugherty plays Noel Kahn in Pretty Little Liars.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

**Shared-assessment control — FULL**

> Brant Daugherty plays Noel Kahn in Pretty Little Liars.

Material assertions supported: `True`; complete fulfilment: `True`; mode/prose agreement: `True`.

Case assessment: The named show/role is Noel Kahn and the alternative Mike attribution is explicitly mistaken. A correction reading supports all factual answers. CFAF output includes literal string "null" in two optional metadata fields; it is retained and not converted to JSON null.
