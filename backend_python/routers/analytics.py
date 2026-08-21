from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
import security
import policy_engine
import relevance
from semantic_graph import build_semantic_cooccurrence_graph
from database import get_db

router = APIRouter(prefix="/api", tags=["Analytics"])


@router.get("/knowledge-map/me")
def get_my_knowledge_map(user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    return build_knowledge_map(user_id, db)


@router.get("/knowledge-map/{requested_user_id}")
def get_knowledge_map(
    requested_user_id: str,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    if requested_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own knowledge map.")
    return build_knowledge_map(user_id, db)


def build_knowledge_map(user_id: str, db: Session):
    try:
        graph = _build_governed_graph(user_id, db)
        return {
            "status": "success",
            "scope": graph["scope"],
            "map": [
                {"keyword": node["keyword"], "count": node["document_frequency"]}
                for node in sorted(graph["nodes"], key=lambda item: (-item["document_frequency"], item["keyword"]))
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/me")
def get_my_ontology(user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    return build_ontology(user_id, db)


@router.get("/semantic-cooccurrence-graph/me")
def get_my_semantic_cooccurrence_graph(user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    return _build_governed_graph(user_id, db)


@router.get("/ontology/{requested_user_id}")
def get_ontology(
    requested_user_id: str,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    if requested_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own semantic graph.")
    return build_ontology(user_id, db)


@router.get("/semantic-cooccurrence-graph/{requested_user_id}")
def get_semantic_cooccurrence_graph(
    requested_user_id: str,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    if requested_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own semantic graph.")
    return _build_governed_graph(user_id, db)


def _build_governed_graph(user_id: str, db: Session) -> dict:
    direct_records = db.query(models.UserDocumentPermission.document_id).filter(
        models.UserDocumentPermission.user_id == user_id,
    ).all()
    public_records = db.query(models.Document.id).filter(
        models.Document.visibility.in_(["Aggregate", "Metadata"]),
        models.Document.source_status == "ACTIVE",
    ).all()
    candidate_ids = sorted({record[0] for record in direct_records + public_records})
    governance = policy_engine.resolve_document_access_bulk(
        db=db,
        user_id=user_id,
        doc_ids=candidate_ids,
        purpose="semantic_graph_visualization",
    )
    visible_ids = sorted(
        doc_id for doc_id in governance["usable_doc_ids"]
        if governance["use_decisions"].get(doc_id) in {relevance.USE_FULL, relevance.USE_METADATA}
    )
    rows = []
    if visible_ids:
        rows = db.query(models.DocumentKeyword.document_id, models.Keyword.word).join(
            models.Keyword, models.Keyword.id == models.DocumentKeyword.keyword_id,
        ).filter(models.DocumentKeyword.document_id.in_(visible_ids)).all()
    document_keywords: dict[str, list[str]] = {doc_id: [] for doc_id in visible_ids}
    for document_id, keyword in rows:
        document_keywords[document_id].append(keyword)
    graph = build_semantic_cooccurrence_graph(document_keywords)
    graph["governance"] = {
        "policy_enforced": True,
        "policy_order": "governance_before_graph_export",
        "included_document_count": len(visible_ids),
    }
    return graph


def build_ontology(user_id: str, db: Session):
    """Compatibility alias for the former endpoint; output is not an ontology."""
    try:
        return _build_governed_graph(user_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
