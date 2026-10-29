"""Conservative query-only segmentation, not a general NLP parser."""
import re
from .contracts import RequestContract, Requirement, ValueType

class LocalProfiler:
    def profile(self, query, as_of=None):
        pieces=[];start=0
        for match in re.finditer(r'\s+(?:and|és)\s+',query,flags=re.I):
            pieces.append((start,match.start()));start=match.end()
        pieces.append((start,len(query)));requirements=[]
        for start,end in pieces:
            while start<end and query[start].isspace():start+=1
            while end>start and query[end-1].isspace():end-=1
            if start==end:continue
            text=query[start:end].casefold()
            kind=ValueType.NUMBER if re.search(r'\b(how many|hány|count|average|mean|sum)\b',text) else ValueType.DATE_TIME if re.search(r'\b(when|date|mikor|dátum)\b',text) else ValueType.ENTITY if re.search(r'\b(who|ki)\b',text) else ValueType.UNKNOWN
            dependency=[requirements[-1].requirement_id] if requirements and re.search(r'\b(he|she|they|that person|ő|neki|annak)\b',text) else []
            requirements.append(Requirement(requirement_id=f'req-{len(requirements)+1}',query_start=start,query_end=end,required=True,value_type=kind,qualifiers=[],depends_on=dependency,exhaustive=bool(re.search(r'\b(all|every|earliest|latest|first|összes|legelső|legutolsó)\b',text))))
        return RequestContract(query=query,as_of=as_of,language='hu' if re.search('[áéíóöőúüű]',query.casefold()) else 'en',logic='UNRESOLVED' if re.search(r'\b(or|vagy)\b',query,re.I) else 'AND',requirements=requirements)
