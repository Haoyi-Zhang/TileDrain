"""Check capacity-universal groups and construct weighted no-least obstructions.

Exact input verdicts come from retained permutation-oracle rows, not from
re-running the diagnosis and calling its own answers a reference.
"""
from __future__ import annotations
import argparse,csv,gzip,itertools,json,time
from pathlib import Path
from contracts import Instance,verify
from robust import effectively_aligned,obstruction_capacity,synthesize_effective
from general import analyze,verify_analysis
from independent import independent_verify_analysis, independent_verify_cut
from oracle import all_forward_posets,structural_cuts
from inputs import instance_from_dict,instance_dict
from experiment import feasible_from_structure
ROOT=Path(__file__).resolve().parents[1]


def exact_groups(source: Path, out: Path, n: int) -> dict:
    ps=list(all_forward_posets(n));groups={};seen_p=set();rows=0
    files=sorted(source.glob(f'exact-{n}-*.json'))
    if not files:raise ValueError('exact result chunks are required first')
    for path in files:
        summary=json.loads(path.read_text())
        selected=set(range(summary['p_start'],summary['p_stop']))
        if seen_p & selected:raise ValueError('overlapping exact chunks')
        seen_p |= selected
        raw=path.with_suffix('.csv.gz')
        with gzip.open(raw,'rt',newline='') as f:
            for row in csv.DictReader(f):
                key=tuple(int(row[k]) for k in ('p','q','lane_bits','unsupported'))
                cap=(int(row['capacity_0']),int(row['capacity_1']))
                current=groups.setdefault(key,{'all_least':True,'capacities':set()})
                if cap in current['capacities']:raise ValueError('duplicate capacity row')
                current['capacities'].add(cap)
                current['all_least'] &= bool(int(row['least']))
                rows+=1
    if seen_p!=set(range(len(ps))):raise ValueError('exact P-index coverage is incomplete')
    robust=0;obstructions=0;effective_instances=0
    with gzip.open(out/f'capacity-groups-{n}.csv.gz','wt',newline='') as f:
        writer=csv.writer(f);writer.writerow(['p','q','lane_bits','unsupported','capacity_instances','all_least','effective_alignment','obstruction_capacity_0','obstruction_capacity_1'])
        for (pi,qi,lb,u), group in sorted(groups.items()):
            lane=tuple(lb>>i&1 for i in range(n))
            expected=set(itertools.product(range(lane.count(0)+1),range(lane.count(1)+1)))
            if group['capacities']!=expected:raise ValueError('missing capacity within a fixed group')
            x=Instance(ps[pi],ps[qi],lane,(1,)*n,(n,n),u)
            ea=effectively_aligned(x)
            if group['all_least']!=ea:raise AssertionError(('capacity robustness mismatch',instance_dict(x)))
            cap=obstruction_capacity(x)
            if ea:
                robust+=1;effective_instances+=len(expected);ob=(-1,-1)
                if cap is not None:raise AssertionError('unnecessary obstruction')
            else:
                if cap is None or cap not in expected:raise AssertionError('missing admitted obstruction')
                y=Instance(x.p,x.q,x.lane,x.weight,cap,u)
                cert=analyze(y)
                if (cert['kind']!='no_least' or not verify_analysis(y,cert) or
                    not independent_verify_analysis(y,cert)):
                    raise AssertionError('constructed vector did not have an independently valid no-least certificate')
                obstructions+=1;ob=cap
            writer.writerow([pi,qi,lb,u,len(expected),int(group['all_least']),int(ea),*ob])
    # Structural group coverage is cross-checked against a direct independent key count.
    expected_groups=sum(1 for p in ps for q in ps if not any(a&~b for a,b in zip(p,q)))*(1<<n)*(1<<n)
    if len(groups)!=expected_groups:raise ValueError('fixed P/Q/lane/unsupported group coverage incomplete')
    return dict(suite='capacity-groups',n=n,fixed_groups=len(groups),capacity_instances=rows,
                robust_groups=robust,effectively_aligned_instances=effective_instances,
                obstruction_vectors=obstructions,mismatches=0)


def weighted_obstructions(out: Path) -> dict:
    cases=json.loads((ROOT/'inputs/weighted.json').read_text());aligned=0;obstructions=0;traces=0
    with gzip.open(out/'weighted-obstructions.jsonl.gz','wt') as f:
        for case in cases:
            x=instance_from_dict(case['instance']);cap=obstruction_capacity(x)
            if cap is None:
                aligned+=1
                certificate=synthesize_effective(x)
                if not verify(x,certificate) or not independent_verify_cut(x,certificate):
                    raise AssertionError('effective certificate failure')
                row={'case':case['case'],'effective_alignment':True,'certificate':certificate}
            else:
                y=Instance(x.p,x.q,x.lane,x.weight,cap,x.unsupported)
                structural,nt=structural_cuts(y.p,y.q,y.lane);traces+=nt
                feasible=feasible_from_structure(y,structural);meet=(1<<y.n)-1
                for d in feasible:meet &= d
                a=analyze(y)
                if (meet in feasible or a['kind']!='no_least' or not verify_analysis(y,a) or
                        not independent_verify_analysis(y,a)):
                    raise AssertionError('weighted obstruction failure')
                obstructions+=1
                row={'case':case['case'],'effective_alignment':False,'instance':instance_dict(y),
                     'certificate':a,'oracle_feasible_masks':feasible}
            f.write(json.dumps(row,sort_keys=True)+'\n')
    return dict(suite='weighted-obstructions',instances=len(cases),effectively_aligned=aligned,
                obstruction_vectors=obstructions,destination_traces_examined=traces,mismatches=0)


def main() -> None:
    import resource
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,choices=range(5));parser.add_argument('--weighted',action='store_true')
    parser.add_argument('--source',type=Path,default=ROOT/'results/campaign')
    parser.add_argument('--output',type=Path,default=ROOT/'results/reproduced')
    a=parser.parse_args()
    if a.weighted==(a.n is not None):parser.error('choose exactly one of --n or --weighted')
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    a.output.mkdir(parents=True,exist_ok=True);cpu=time.process_time();wall=time.perf_counter()
    result=weighted_obstructions(a.output) if a.weighted else exact_groups(a.source,a.output,a.n)
    result.update(cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    name='weighted-obstructions' if a.weighted else f'capacity-groups-{a.n}'
    (a.output/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
