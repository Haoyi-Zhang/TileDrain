"""Reconcile retained raw rows and produce the manuscript's numerical inputs."""
from __future__ import annotations
import argparse,csv,gzip,json,statistics
from pathlib import Path
from oracle import all_forward_posets
ROOT=Path(__file__).resolve().parents[1]

EXACT_FIELDS=('instances','structures','destination_traces_examined','feasible_cuts','least','no_least',
              'aligned','effectively_aligned','capability_only_unsafe','capability_order_unsafe',
              'least_drained_events','all_drain_events','oracle_mismatches','certificate_failures',
              'independent_certificate_failures')


def aggregate(folder:Path,output:Path) -> dict:
    exact=[];groups=[]
    for n in range(5):
        chunks=[json.loads(p.read_text()) for p in sorted(folder.glob(f'exact-{n}-*.json'))]
        if not chunks:raise ValueError('missing exact chunks for n='+str(n))
        indices=[]
        row={'n':n,**{k:sum(c[k] for c in chunks) for k in EXACT_FIELDS}}
        for c in chunks:
            indices.extend(range(c['p_start'],c['p_stop']))
            path=folder/f"exact-{n}-{c['p_start']:02d}-{c['p_stop']:02d}.csv.gz"
            observed={k:0 for k in ('instances','least','no_least','feasible_cuts','capability_only_unsafe','capability_order_unsafe','least_drained_events','all_drain_events')}
            with gzip.open(path,'rt',newline='') as f:
                for r in csv.DictReader(f):
                    least=int(r['least']);observed['instances']+=1
                    observed['least']+=least;observed['no_least']+=1-least
                    observed['feasible_cuts']+=int(r['feasible_count'])
                    observed['capability_only_unsafe']+=1-int(r['capability_only_safe'])
                    observed['capability_order_unsafe']+=1-int(r['capability_order_safe'])
                    if least:
                        observed['least_drained_events']+=int(r['drain_or_left']).bit_count()
                        observed['all_drain_events']+=n
            if any(observed[k]!=c[k] for k in observed):raise ValueError('raw/summary disagreement: '+str(path))
        if sorted(indices)!=list(range(len(list(all_forward_posets(n))))):raise ValueError('exact P index coverage gap or overlap')
        if row['instances']!=row['least']+row['no_least'] or row['oracle_mismatches'] or row['certificate_failures'] or row['independent_certificate_failures']:
            raise ValueError('invalid exact suite summary')
        exact.append(row)
        group=json.loads((folder/f'capacity-groups-{n}.json').read_text())
        if group['capacity_instances']!=row['instances'] or group['effectively_aligned_instances']!=row['effectively_aligned'] or group['mismatches']:
            raise ValueError('capacity group mismatch')
        groups.append({k:group[k] for k in ('n','fixed_groups','capacity_instances','robust_groups','effectively_aligned_instances','obstruction_vectors','mismatches')})
    result={'exact_by_n':exact,'exact_totals':{k:sum(r[k] for r in exact) for k in EXACT_FIELDS},
            'capacity_groups_by_n':groups,'capacity_group_totals':{k:sum(r[k] for r in groups) for k in groups[0] if k!='n'}}
    for name in ('weighted','weighted-exhaustive','arithmetic','episodes','mutations','weighted-obstructions','scaling'):
        x=json.loads((folder/(name+'.json')).read_text())
        result[name]={k:v for k,v in x.items() if k not in ('cpu_seconds','wall_seconds','peak_rss_kib','workers')}
        if any(v for k,v in x.items() if isinstance(v,(int,float)) and any(s in k for s in ('mismatches','failures','unexpected_outcomes','duplicate_or_missing','order_violations'))):
            raise ValueError('recorded scientific failure: '+name)
        if name=='weighted-exhaustive':
            bad=sum(row[k] for row in x['by_n'] for k in row if any(s in k for s in ('mismatches','failures')))
            if bad:raise ValueError('recorded scientific failure: '+name)
    with (folder/'scaling.csv').open(newline='') as f:raw=list(csv.DictReader(f))
    medians=[]
    for n in (16,32,64,128,256,512):
        for density in ('sparse','dense'):
            selected=[r for r in raw if int(r['n'])==n and r['density']==density]
            if len(selected)!=3:raise ValueError('incomplete scaling cell')
            medians.append({'n':n,'density':density,**{k:statistics.median(float(r[k])*1000 for r in selected)
                           for k in ('general_cpu_seconds','check_cpu_seconds','aligned_cpu_seconds')}})
    result['scaling_median_ms']=medians
    output.mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (output/'exact-by-n.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(exact[0]));w.writeheader();w.writerows(exact)
    with (output/'capacity-groups-by-n.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(groups[0]));w.writeheader();w.writerows(groups)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'results/campaign')
    p.add_argument('--output',type=Path,default=ROOT/'results/summary');a=p.parse_args()
    r=aggregate(a.source,a.output);print(json.dumps({'exact':r['exact_totals'],'capacity_groups':r['capacity_group_totals']},indent=2))
