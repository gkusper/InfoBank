"""Conservative, schema-driven structured requests; no numbers are extracted from prose."""
from dataclasses import dataclass,field
import datetime,json,re,math
from .contracts import *
from .structured import shortcut,aggregate
from .adapters.local import digest,canonical

FIELDS={'file_type':('TEXT',['file type','document type','file format','file_type']), 'created_at':('DATE_TIME',['creation date','creation time','created date','created_at','creation year']), 'updated_at':('DATE_TIME',['modification date','modification time','modified date','last modified','updated_at'])}

def normalized(text):return ' '.join(re.findall(r'[\w-]+',text.casefold()))
def title_alias(title):
    text=normalized(title or '')
    return re.sub(r'\s+(?:metadata card|summary report|document|report|metadata|file)$','',text).strip()
def contains(text,phrase):return bool(re.search(r'(?<!\w)'+re.escape(normalized(phrase))+r'(?!\w)',normalized(text)))
def operation(query):
    q=normalized(query)
    found=[op for op,words in {'count':['how many','number of','count of'],'sum':['sum of','total of','total'],'mean':['mean','average']}.items() if any(contains(q,w) for w in words)]
    return found[0] if len(found)==1 else None

@dataclass
class Resolution:
    proposal: LLMProposal | None = None
    blocked: bool = False
    permitted_restricted: dict = field(default_factory=dict)
    audit: dict = field(default_factory=lambda:{'status':'NOT_STRUCTURED'})

class StructuredRequestResolver:
    def _binding(self,request,evidence):
        bindings=evidence.structured_bindings;views={v.source_id:v for v in evidence.views};a=evidence.authority
        target=re.split(r'\b(?:for|about|of)\b',request.query,flags=re.I)[-1].strip(' ?.!\"\'')
        target=re.sub(r'\s+(?:in|during)\s+\d{4}\s*$','',target,flags=re.I);wanted=title_alias(target)
        candidates=[];all_names=[]
        for b in bindings:
            if any(b.get(k)!=getattr(a,k) for k in ['principal','purpose','policy_version','revocation_version']):continue
            if b['source_id'] not in views:continue
            names=[normalized(s) for s in b.get('target_names',[]) if s] or [title_alias(b.get('catalogue_title'))]
            all_names.extend((b['source_id'],name) for name in names if name)
            if wanted and wanted in names:candidates.append(b)
        if len(candidates)!=1:return None
        chosen=candidates[0]
        if any(sid!=chosen['source_id'] and name.startswith(wanted+' ') for sid,name in all_names):return None
        return chosen
    def resolve(self,request,evidence):
        if evidence.structured_signature and evidence.structured_signature!=digest(canonical(evidence.structured_bindings)):raise ValueError('STALE_STRUCTURED_BINDING')
        if request.logic!='AND':return Resolution(audit={'status':'UNRESOLVED_LOGIC'})
        # Preserve the explicit legacy compatibility API; NL shortcuts below require target binding.
        legacy=shortcut(request,evidence)
        if legacy:return Resolution(proposal=legacy,audit={'status':'LEGACY_EXPLICIT_APPLICATION_SNAPSHOT'})
        q=request.query;fields=[]
        for key,(kind,aliases) in FIELDS.items():
            if any(contains(q,alias) for alias in aliases):fields.append(key)
        op=operation(q)
        if not fields and not op:return Resolution()
        if not any(v.view_kind==('metadata' if fields else 'aggregate') for v in evidence.views):return Resolution()
        binding=self._binding(request,evidence)
        if not binding:return Resolution(blocked=all(v.view_kind!='content' for v in evidence.views),audit={'status':'TARGET_UNRESOLVED_OR_AMBIGUOUS'})
        view=next(v for v in evidence.views if v.source_id==binding['source_id'])
        if fields and view.view_kind=='metadata':return self._metadata(request,evidence,view,fields)
        if op and view.view_kind=='aggregate':
            spec=binding.get('aggregate_spec')
            if spec:return self._aggregate(request,evidence,view,spec,op)
            # A pre-authorized prose aggregate is evidence for one model call, never trusted numeric data.
            if op=='count' and len(request.requirements)==1 and not request.requirements[0].depends_on:
                return Resolution(permitted_restricted={view.source_id:[request.requirements[0].requirement_id]},audit={'status':'AUTHORIZED_AGGREGATE_PROSE_MODEL_REQUIRED','trusted_numeric_computation':False})
        return Resolution(audit={'status':'STRUCTURED_VIEW_OR_SCOPE_UNAVAILABLE'})
    def _proposal(self,request,view,text,value,kind,quotes=None):
        quotes=quotes or [view.text]
        refs=[EvidenceRef(source_id=view.source_id,quote=q) for q in quotes]
        claims=[];support=[]
        for i,r in enumerate(request.requirements):
            c=Claim(claim_id=f'structured-{i+1}',requirement_ids=[r.requirement_id],text=text,value_type=r.value_type if r.value_type!=ValueType.UNKNOWN else kind,value=str(value),subject_key=None,dependencies=[],evidence=refs);claims.append(c);support.append(RequirementSupport(requirement_id=r.requirement_id,status='SUFFICIENT',claim_ids=[c.claim_id],missing=''))
        p=LLMProposal(requirements=request.requirements,source_assessments=[SourceAssessment(source_id=view.source_id,role='PRIMARY',relation='SUPPORTS',grounding_span_ids=[],grounding_quotes=quotes,note='Application-verified structured operation')],claims=claims,requirement_support=support,interpretation_limit='')
        return Resolution(proposal=p,audit={'status':'TRUSTED_STRUCTURED_COMPLETE','fields_checked_locally':True})
    def _metadata(self,request,evidence,view,fields):
        prefix=re.split(r'\b(?:for|about|of)\b',request.query,flags=re.I)[0];remainder=normalized(prefix)
        for key in fields:
            for alias in FIELDS[key][1]:remainder=re.sub(r'(?<!\w)'+re.escape(normalized(alias))+r'(?!\w)',' ',remainder)
        words=set(re.findall(r'\w+',remainder))-{'what','which','is','are','the','a','an','and','recorded','give','show','please','tell','me','exact','full','timestamp','year'}
        if words:return Resolution(blocked=True,audit={'status':'UNSUPPORTED_ESSENTIAL_METADATA_FIELD'})
        data=json.loads(view.text);values=[];date_value=None
        for key in fields:
            value=data.get(key);kind=FIELDS[key][0]
            if not isinstance(value,str) or not value.strip():return Resolution(blocked=True,audit={'status':'MISSING_OR_INVALID_METADATA_VALUE'})
            if kind=='DATE_TIME':
                try:dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
                except ValueError:return Resolution(blocked=True,audit={'status':'INVALID_METADATA_DATE'})
                if re.search(r'\b(?:time|timestamp)\b',prefix,re.I) and 'T' not in value:return Resolution(blocked=True,audit={'status':'REQUESTED_TIME_PRECISION_UNAVAILABLE'})
                if re.search(r'\byear\b',prefix,re.I):value=str(dt.year)
                date_value=value
            values.append(f'{key}: {value}')
        quotes=[json.dumps(k,ensure_ascii=True)+':'+json.dumps(data[k],ensure_ascii=True,separators=(',',':')) for k in fields]
        return self._proposal(request,view,'; '.join(values),date_value or data[fields[0]],ValueType.DATE_TIME if date_value else ValueType.TEXT,quotes)
    def _aggregate(self,request,evidence,view,spec,op):
        a=evidence.authority
        if any(spec.get(k)!=getattr(a,k) for k in ['principal','purpose','policy_version','revocation_version']):return Resolution(blocked=True,audit={'status':'STALE_AGGREGATE_AUTHORITY'})
        required=['metric','unit','population','rows','k','period_start','period_end']
        if any(k not in spec for k in required):return Resolution(blocked=True,audit={'status':'INCOMPLETE_AGGREGATE_CONTRACT'})
        if not any(contains(request.query,s) for s in [spec['metric'],*spec.get('metric_aliases',[])]) or not any(contains(request.query,s) for s in [spec['unit'],*spec.get('unit_aliases',[])]):return Resolution(blocked=True,audit={'status':'METRIC_OR_UNIT_UNRESOLVED'})
        if not spec['population'] or type(spec['k']) is not int or spec['k']<2:return Resolution(blocked=True,audit={'status':'INVALID_POPULATION_OR_THRESHOLD'})
        if op=='count' and spec.get('countable') is not True:return Resolution(blocked=True,audit={'status':'COUNT_METRIC_NOT_ATTESTED'})
        prefix=re.split(r'\b(?:for|about)\b',request.query,flags=re.I)[0];rest=normalized(prefix)
        phrases=[spec['metric'],spec['unit'],*spec.get('metric_aliases',[]),*spec.get('unit_aliases',[]),'how many','number of','count of','sum of','total of','count','sum','total','mean','average']
        for phrase in sorted(phrases,key=len,reverse=True):rest=re.sub(r'(?<!\w)'+re.escape(normalized(phrase))+r'(?!\w)',' ',rest)
        if set(re.findall(r'\w+',rest))-{'what','is','are','the','a','an','please','give','show','me'}:return Resolution(blocked=True,audit={'status':'UNSUPPORTED_ESSENTIAL_AGGREGATE_QUALIFIER'})
        years=re.findall(r'\b(?:in|during)\s+(\d{4})\b',request.query,re.I)
        if years and (len(set(years))!=1 or spec['period_start']!=years[0]+'-01-01' or spec['period_end']!=years[0]+'-12-31'):return Resolution(blocked=True,audit={'status':'TEMPORAL_SCOPE_MISMATCH'})
        rows=[];policies={}
        for row in spec['rows']:
            if row.get('unit')!=spec['unit'] or type(row.get('value')) not in {int,float} or not math.isfinite(row['value']) or not row.get('contributor_id') or not row.get('source_id'):return Resolution(blocked=True,audit={'status':'INVALID_CONTRIBUTION_OR_UNIT'})
            if years:
                try:day=datetime.date.fromisoformat(row.get('date',''))
                except ValueError:return Resolution(blocked=True,audit={'status':'MISSING_CONTRIBUTION_TIME'})
                if not datetime.date.fromisoformat(spec['period_start'])<=day<=datetime.date.fromisoformat(spec['period_end']):continue
            rows.append({k:row[k] for k in ['source_id','contributor_id','value']});policies[row['source_id']]={'FULL':'full','AGGREGATE':'aggregate'}.get(row.get('access_mode'),'deny')
        result=aggregate(rows,policies,op,spec['k'])
        if result['aggregate'] is None:return Resolution(blocked=True,audit={'status':'AGGREGATE_THRESHOLD_NOT_MET'})
        try:data=json.loads(view.text)
        except ValueError:return Resolution(blocked=True,audit={'status':'STRUCTURED_SNAPSHOT_REQUIRED'})
        value=result['aggregate']['value']
        if any(data.get(k)!=v for k,v in {'operation':op,'metric':spec['metric'],'unit':spec['unit'],'population':spec['population'],'value':value}.items()):return Resolution(blocked=True,audit={'status':'AGGREGATE_SNAPSHOT_MISMATCH'})
        return self._proposal(request,view,f"{op} {spec['metric']}: {value} {spec['unit']}",value,ValueType.NUMBER)
