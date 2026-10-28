"""Reproduce structurally selected fixtures before any hosted calls."""
import itertools,json,random
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix

def oracle(nodes,edges,prior,restrict=False,exclude=None):
 rows=[];lo=[];hi=[]
 def row(items,l,u): rows.append(dict(items));lo.append(l);hi.append(u)
 for i in range(len(nodes)):row([(3*i+c,1) for c in range(3)],1,1)
 for a,b in edges:
  i,j=nodes.index(a),nodes.index(b)
  for c in range(3):row([(3*i+c,1),(3*j+c,1)],-np.inf,1)
 row([(0,1)],1,1)
 if restrict:
  active={n for a,b in edges if prior[a]==prior[b] for n in (a,b)}
  for i,n in enumerate(nodes):
   if n not in active:row([(3*i+prior[n],1)],1,1)
 if exclude:row([(3*i+exclude[n],1) for i,n in enumerate(nodes)],-np.inf,len(nodes)-1)
 mat=lil_matrix((len(rows),3*len(nodes)))
 for i,r in enumerate(rows):
  for j,v in r.items():mat[i,j]=v
 result=milp(np.array([int(c!=prior[n]) for n in nodes for c in range(3)]),integrality=np.ones(3*len(nodes)),bounds=Bounds(0,1),constraints=LinearConstraint(mat.tocsr(),lo,hi),options={'time_limit':30,'mip_rel_gap':0})
 if result.status==2:return None
 assert result.success and result.mip_gap==0,(result.message,result.fun)
 colors={n:int(np.argmax(result.x[3*i:3*i+3])) for i,n in enumerate(nodes)}
 assert colors['A']==0 and all(colors[a]!=colors[b] for a,b in edges)
 return int(round(result.fun)),colors

from ebrt_hard_oracle import exact_minimum as exact

def main():
 import argparse
 parser=argparse.ArgumentParser(description='Offline MILP-checked hard-case construction; requires scipy==1.17.0.')
 parser.add_argument('--output', required=True)
 args=parser.parse_args()
 cases=[]
 for n in (24,36,48):
  nodes=['A']+[f'N{i:02}' for i in range(1,n)]
  for attempt in range(1,201):
   seed=260000+n*100+attempt;rng=random.Random(seed)
   prior={x:rng.randrange(3) for x in nodes};prior['A']=0
   target={x:rng.randrange(3) for x in nodes};target['A']=0
   edges=[list(e) for e in itertools.combinations(nodes,2) if target[e[0]]!=target[e[1]] and rng.random()<6.5/(n-1)]
   added=[e for e in edges if prior[e[0]]==prior[e[1]]]
   active={x for e in added for x in e}
   if len(added)<3 or len(active)==n:continue
   probe={'nodes':nodes,'edges':edges,'prior':prior,'added':added}
   optimum,visits=exact(probe)
   if visits < {24:200,36:500,48:1000}[n]:continue
   best=oracle(nodes,edges,prior)
   assert optimum==best[0]
   if best[0]<n//3:continue
   alternative=oracle(nodes,edges,prior,exclude=best[1])
   if alternative is None or alternative[0]!=best[0]:continue
   local=oracle(nodes,edges,prior,restrict=True)
   if local is not None and local[0]==best[0]:continue
   case={'id':f'hard-{n}','seed':seed,'search_states':visits,'nodes':nodes,'edges':edges,'prior':prior,'added':added,'minimum_changes':best[0],'restricted_minimum':local[0] if local else None,'witnesses':[best[1],alternative[1]]}
   cases.append(case);print(n,seed,len(edges),len(added),best[0],None if local is None else local[0],visits,flush=True);break
  else:raise RuntimeError('No case')
 with open(args.output, 'x') as output: output.write(json.dumps(cases,indent=2)+'\n')

if __name__=='__main__': main()
