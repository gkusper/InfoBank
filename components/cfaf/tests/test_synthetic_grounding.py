"""Szintetikus tesztesetek a forrástámasz és entitás-összefüggések vizsgálatához.

A junior feladatátadás specifikációja alapján:
1. Első teszteset (pozitív): Az eredeti kérdés mutatja meg, hogy a válasz
   teljesítette-e a kérést, a dokumentum pedig a válasz tényállítását igazolja (FULL mód).
2. Második teszteset (negatív/ütközés): Két pontos idézet két külön személyről szól,
   ezért együtt sem igazolhatnak egyetlen személyre vonatkozó állítást (CFAF mód).
"""
import pytest
from component_cfaf.contracts import (
    Authority,
    Claim,
    DependencyBinding,
    EvidenceRef,
    LLMProposal,
    ProviderResult,
    RawSource,
    RequirementSupport,
    SourceAssessment,
    ValueType,
)
from component_cfaf.pipeline import Pipeline
from component_cfaf.render import NO_SUPPORT


def test_synthetic_valid_grounding(authority, governance):
    """1. Szintetikus teszteset:
    A kérdés egy konkrét tényre kérdez rá, a modell által adott válasz
    pontosan kielégíti a kérést, a dokumentum pedig igazolja a tényállítást.
    Elvárt eredmény: FULL mód, sikeres státusz, pontos idézet a hivatkozásokban.
    """
    # 1. Forrásdokumentum az igazoló ténnyel
    doc = RawSource(
        private_id='doc-vessel-01',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )

    query = 'What color is the expedition vessel?'

    # 2. Stub modell-szolgáltató: helyes, dokumentumhoz kötött javaslatot ad vissza
    class ValidGroundingProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            quote = 'The expedition vessel is blue.'
            ref = EvidenceRef(source_id=view.source_id, quote=quote)

            claim = Claim(
                claim_id='claim-1',
                requirement_ids=[request.requirements[0].requirement_id],
                text='The expedition vessel is blue.',
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[ref]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_span_ids=[],
                grounding_quotes=[quote],
                note='Direct verbatim factual support'
            )
            support = RequirementSupport(
                requirement_id=request.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['claim-1'],
                missing=''
            )
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim],
                requirement_support=[support],
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 15, 'output_tokens': 15},
                raw=None
            )

    # 3. Pipeline futtatása
    pipeline = Pipeline(governance, ValidGroundingProvider())
    result = pipeline.run(query, [doc], authority)

    # 4. Ellenőrzések (DoD):
    # - A kérés teljesült, a mód FULL
    assert result.response.mode == 'FULL'
    assert result.decision.gate_status == 'GATE_ACCEPTED_FULL'
    assert result.response.text == 'The expedition vessel is blue.'
    
    # - A hivatkozások pontosan tartalmazzák az igazoló forrásrészletet
    assert len(result.response.citations) == 1
    citation = result.response.citations[0]
    assert citation.quote == 'The expedition vessel is blue.'
    assert citation.source_id == 'view-0001'
    assert 'REFERENCE_VALID' in citation.labels
    assert 'SUPPORT_NOT_INDEPENDENTLY_VERIFIED' in citation.labels
    
    # - Nincs hiányzó követelmény
    assert result.decision.missing_requirement_ids == []


def test_synthetic_cross_entity_conflict(authority, governance):
    """2. Szintetikus teszteset:
    Két pontos, szó szerinti idézet két külön személyről szól a forrásban.
    Ezért együtt nem igazolhatnak egyetlen személyre vonatkozó összetett állítást.
    Elvárt eredmény: CFAF tartózkodás (NO_SUPPORT sablon).
    """
    # 1. A forrásban két külön személy szerepel két külön állítással:
    # Ada vezette a projektet, de a feladatokat Bob zárta le!
    doc = RawSource(
        private_id='doc-team-01',
        content='Ada led the project. Bob closed 3 tasks.',
        metadata={'title': 'Team Progress'},
        public_metadata={'title': 'Team Progress'}
    )

    # A kérdés egyazon személyre (she) kérdez rá: ki vezette és ő hány feladatot zárt le
    query = 'Who led the project and how many tasks did she close?'

    # 2. Stub modell-szolgáltató:
    # Mindkét idézet pontosan benne van a forrásban, de az entitások eltérnek:
    # 1. állítás: Ada (vezette a projektet)
    # 2. állítás: Bob (zárta le a 3 feladatot) -> a modell mégis össze akarja vonni
    class CrossEntityConflictProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            quote_ada = 'Ada led the project.'
            quote_bob = 'Bob closed 3 tasks.'

            ref_ada = EvidenceRef(source_id=view.source_id, quote=quote_ada)
            ref_bob = EvidenceRef(source_id=view.source_id, quote=quote_bob)

            req_leader = request.requirements[0]
            req_tasks = request.requirements[1]

            # Claim 1: Ada vezette a projektet
            claim_leader = Claim(
                claim_id='c-leader',
                requirement_ids=[req_leader.requirement_id],
                text='Ada led the project.',
                value_type=ValueType.ENTITY,
                value='Ada',
                subject_key='Ada',
                dependencies=[],
                evidence=[ref_ada]
            )

            # Claim 2: A modell Bob feladatait próbálja bekötni, ahol az entitás nem Ada, hanem Bob!
            claim_tasks_bob = Claim(
                claim_id='c-tasks',
                requirement_ids=[req_tasks.requirement_id],
                text='Bob closed 3 tasks.',
                value_type=ValueType.NUMBER,
                value='3',
                subject_key='Bob',  # ENTITÁS ELTÉRÉS: nem egyezik a szülő állítás alanyával (Ada)!
                dependencies=[
                    DependencyBinding(
                        parent_requirement_id=req_leader.requirement_id,
                        parent_claim_id='c-leader',
                        subject_key='Bob'  # Mismatched subject_key vs parent value ('Ada')
                    )
                ],
                evidence=[ref_bob]
            )

            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_span_ids=[],
                grounding_quotes=[quote_ada, quote_bob],
                note='Both quotes exist in source text'
            )
            supports = [
                RequirementSupport(
                    requirement_id=req_leader.requirement_id,
                    status='SUFFICIENT',
                    claim_ids=['c-leader'],
                    missing=''
                ),
                RequirementSupport(
                    requirement_id=req_tasks.requirement_id,
                    status='SUFFICIENT',
                    claim_ids=['c-tasks'],
                    missing=''
                )
            ]
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim_leader, claim_tasks_bob],
                requirement_support=supports,
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 20, 'output_tokens': 20},
                raw=None
            )

    # 3. Pipeline futtatása
    pipeline = Pipeline(governance, CrossEntityConflictProvider())
    result = pipeline.run(query, [doc], authority)

    # 4. Ellenőrzések (DoD):
    # - A kapu észleli az entitásütközést: a 'req-2' (feladatok száma) nem teljesíthető Adára!
    assert result.response.mode == 'CFAF'
    assert result.decision.gate_status == 'GATE_REQUIRED_CFAF'
    assert result.response.text == NO_SUPPORT
    
    # - A hiányzó/elutasított követelmények között ott van a függő követelmény
    assert 'req-2' in result.decision.missing_requirement_ids
    
    # - CFAF módban nincsenek kiadott idézetek
    assert result.response.citations == []
