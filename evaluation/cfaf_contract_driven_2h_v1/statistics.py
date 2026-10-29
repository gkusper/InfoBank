"""Preregistered grouped statistics; no model calls or semantic truth invention."""
import random,collections

def quantile(values,p):
 if not values:return None
 v=sorted(values);x=(len(v)-1)*p;i=int(x);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)
def bootstrap_groups(rows,seed=20261029,repetitions=2000):
 groups=collections.defaultdict(list)
 for r in rows:groups[r['group']].append(r)
 names=sorted(groups);rng=random.Random(seed);acc={k:[] for k in ['A','B','C']};deltas={k:[] for k in ['C-A','C-B','B-A']}
 if not names:return {'groups':0,'intervals':{}}
 for _ in range(repetitions):
  sample=[r for group in rng.choices(names,k=len(names)) for r in groups[group]];means={s:sum(r[s] for r in sample)/len(sample) for s in acc}
  for s in acc:acc[s].append(means[s])
  for pair in deltas:left,right=pair.split('-');deltas[pair].append(means[left]-means[right])
 return {'method':'Percentile cluster bootstrap, groups resampled jointly for systems; failures retained','seed':seed,'replicates':repetitions,'groups':len(names),'intervals':{s:[quantile(v,.025),quantile(v,.975)] for s,v in acc.items()},'paired_delta_intervals':{s:[quantile(v,.025),quantile(v,.975)] for s,v in deltas.items()},'population_or_significance_claim':False}

def paired_counts(rows,left='C',right='B'):
 both=sum(r[left] and r[right] for r in rows);left_only=sum(r[left] and not r[right] for r in rows);right_only=sum(r[right] and not r[left] for r in rows);neither=len(rows)-both-left_only-right_only
 return {'N':len(rows),'both_mode_correct_nonoperational':both,'left_only':left_only,'right_only':right_only,'neither':neither,'difference_count':left_only-right_only,'difference_fraction':(left_only-right_only)/len(rows) if rows else None,'left':left,'right':right}
