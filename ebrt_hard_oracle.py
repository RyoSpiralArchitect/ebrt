"""Exact minimum-edit search, independent of the optional MILP fixture generator."""

def exact_minimum(f, restricted=False):
 nodes=f['nodes'];idx={n:i for i,n in enumerate(nodes)};adj=[set() for n in nodes]
 for a,b in f['edges']:adj[idx[a]].add(idx[b]);adj[idx[b]].add(idx[a])
 prior=[f['prior'][n] for n in nodes];active={idx[n] for e in f['added'] for n in e}
 assigned={0:0}; best=len(nodes)+1; witness=None;visited=0
 def search(cost):
  nonlocal best,witness,visited
  visited+=1
  if visited>2000000:raise RuntimeError('Search cap')
  remaining=[i for i in range(len(nodes)) if i not in assigned]
  banned={i:{assigned[j] for j in adj[i] if j in assigned} for i in remaining}
  if cost+sum(prior[i] in banned[i] for i in remaining)>=best:return
  if not remaining:best=cost;witness=dict(assigned);return
  i=max(remaining,key=lambda x:(len(banned[x]),len(adj[x]),x))
  choices=[prior[i]] if restricted and i not in active else [prior[i]]+[c for c in range(3) if c!=prior[i]]
  for c in choices:
   if c not in banned[i]:
    assigned[i]=c;search(cost+(c!=prior[i]));del assigned[i]
 search(0)
 return (best if witness is not None else None),visited
