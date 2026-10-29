"""Authorized projection before retrieval; no backend/Pydantic-V1 import."""
import hashlib,json,re,sqlite3,threading
from .legacy_projection import project_case
from ..contracts import *

PROCESSING_VERSION='component-cfaf-view-v1.1'
def digest(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def make_view(source_id,kind,text,public_metadata=None):
    h=digest(text)
    spans=[Span(span_id=f'{source_id}:span-{i+1:04d}',start=start,end=min(start+600,len(text)),content_sha256=h) for i,start in enumerate(range(0,len(text),600))]
    return View(source_id=source_id,view_kind=kind,text=text,content_sha256=h,spans=spans,public_metadata=public_metadata or {})

class LegacyGovernance:
    """The resolver must be an authenticated application policy decision, never LLM data."""
    def __init__(self,resolver,current=None):
        self.resolver=resolver;self.is_current=current or (lambda a:True)
    def current(self,authority):return bool(self.is_current(authority))
    def project(self,query,sources,authority):
        if not self.current(authority):raise ValueError('POLICY_REVOKED')
        raw=[];excluded=[];blocked=[];decisions={};by_private={s.private_id:s for s in sources}
        if len(by_private)!=len(sources):raise ValueError('DUPLICATE_PRIVATE_SOURCE')
        for s in sources:
            d=self.resolver(s,authority)
            decisions[s.private_id]=d
            if not isinstance(d,AccessDecision):raise ValueError('AUTHENTICATED_POLICY_RESULT_REQUIRED')
            if d.access=='DENY' or not d.existence_public or not d.compatible or not d.clean:
                excluded.append({'original_source_id':s.private_id,'included':False,'access_mode':d.access})
                blocked.extend([s.private_id,s.content,*s.private_markers]);continue
            raw.append({'protected_markers':s.private_markers,'source_id':s.private_id,'content':s.content,'metadata':s.metadata,'source_type':s.source_type,'access_mode':d.access,'existence_visibility':'PUBLIC' if d.existence_public else 'NONE','allowed_metadata_fields':d.metadata_fields,'aggregate_view':d.aggregate_view,'purpose_compatibility':'compatible' if d.compatible else 'incompatible','security_status':'clean' if d.clean else 'unsafe','policy_rule_id':authority.policy_version})
        request=project_case({'query':query,'sources':raw})
        included={p['permitted_source_id']:p['original_source_id'] for p in request.internal_policy if p['included']}
        views=[make_view(d['source_id'],d['view_kind'],d['context'],{k:v for k,v in by_private[included[d['source_id']]].public_metadata.items() if k in {'title','url'} and isinstance(v,str)}) for d in request.documents]
        bindings=[{'source_id':sid,'target_names':decisions[pid].target_names,'catalogue_title':by_private[pid].catalogue_title,'aggregate_spec':decisions[pid].aggregate_spec,'policy_version':authority.policy_version,'revocation_version':authority.revocation_version,'principal':authority.principal,'purpose':authority.purpose} for sid,pid in included.items()]
        return views,{'structured_bindings':bindings,'policy':request.internal_policy+excluded,'private_mapping':included,'blocked_values':request.blocked_values+blocked}

class ProvidedContextRetriever:
    def retrieve(self,request,permitted):return list(permitted)

class SQLiteRetriever:
    """Only authorized views enter this short-lived in-memory index."""
    def __init__(self,limit=5):
        if limit<1:raise ValueError('POSITIVE_RETRIEVAL_LIMIT_REQUIRED')
        self.limit=limit
    def retrieve(self,request,permitted):
        if not permitted:return []
        terms=list(dict.fromkeys(re.findall(r'\w+',request.query,flags=re.UNICODE)))[:64]
        if not terms:return list(permitted)[:self.limit]
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE VIRTUAL TABLE docs USING fts5(content)')
            db.executemany('INSERT INTO docs(rowid,content) VALUES (?,?)',[(i+1,v.text) for i,v in enumerate(permitted)])
            expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
            ranked=db.execute('SELECT rowid FROM docs WHERE docs MATCH ? ORDER BY bm25(docs),rowid LIMIT ?',(expression,self.limit)).fetchall()
        chosen={r[0]-1 for r in ranked}
        return [v for i,v in enumerate(permitted) if i in chosen]

class QuotaLedger:
    """Application-memory demo ledger; a production service supplies its durable equivalent."""
    def __init__(self,limit=100):self.limit=limit;self.used={};self.requests={};self.lock=threading.Lock()
    def consume(self,authority,query):
        key=(authority.principal,authority.purpose);rid=key+(authority.request_id,);signature=digest(canonical([query,authority.policy_version,authority.revocation_version]))
        with self.lock:
            if rid in self.requests:
                if self.requests[rid]!=signature:raise ValueError('REQUEST_ID_REUSED_WITH_DIFFERENT_SCOPE')
                raise ValueError('QUERY_ALREADY_CONSUMED')
            if self.used.get(key,0)>=self.limit:raise ValueError('QUERY_QUOTA_EXCEEDED')
            self.used[key]=self.used.get(key,0)+1;self.requests[rid]=signature

def evidence_contract(authority,all_views,selected,complete_scope=False):
    byid={v.source_id:v for v in all_views}
    if len(byid)!=len(all_views) or len({v.source_id for v in selected})!=len(selected):raise ValueError('DUPLICATE_VIEW')
    if any(v.source_id not in byid or v!=byid[v.source_id] for v in selected):raise ValueError('RETRIEVER_CHANGED_AUTHORIZED_VIEW')
    ids={v.source_id for v in selected}
    key=digest(canonical([authority.principal,authority.purpose,authority.policy_version,authority.revocation_version,PROCESSING_VERSION,[(v.source_id,v.content_sha256,v.view_kind) for v in all_views],sorted(ids),complete_scope]))
    return GovernedEvidenceContract(authority=authority,views=selected,inventory=[InventoryEntry(source_id=v.source_id,view_kind=v.view_kind,content_sha256=v.content_sha256,supplied=v.source_id in ids) for v in all_views],cache_key=key,processing_version=PROCESSING_VERSION,complete_scope=complete_scope)
