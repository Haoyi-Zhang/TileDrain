"""Single-worker, bounded, resumable scientific campaign.

Results describe generated finite machines and Python checking costs only.
Invoke separate chunks as documented in README.md; no scientific subprocesses.
"""
from __future__ import annotations
import argparse,csv,gzip,itertools,json,os,platform,sys,time
from dataclasses import replace
from pathlib import Path
from contracts import Instance,bits,closure,lower_closure,safe,synthesize,verify
from robust import effectively_aligned, synthesize_effective
from general import analyze,verify_analysis
from independent import independent_verify_analysis
from oracle import all_forward_posets,structural_cuts,feasible_from_structure
from inputs import instance_from_dict,instance_dict
from semantics import OPS,capability,reference_alu,adapter_alu,encode_state,decode_state
from simulator import run_epoch

ROOT=Path(__file__).resolve().parents[1]


def _cpu_model() -> str | None:
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.is_file():
        fields: dict[str, str] = {}
        for line in cpuinfo.read_text(encoding='utf-8', errors='replace').splitlines():
            key, separator, value = line.partition(':')
            if separator and value.strip():
                fields.setdefault(key.strip().lower(), value.strip())
        for key in ('model name', 'hardware', 'cpu model'):
            if fields.get(key):
                return fields[key]
        processor = fields.get('processor')
        if processor and not processor.isdecimal():
            return processor
    value = platform.processor().strip()
    return value or None


def _visible_container_markers() -> list[str]:
    markers: list[str] = []
    for path, label in ((Path('/.dockerenv'), '/.dockerenv'), (Path('/run/.containerenv'), '/run/.containerenv')):
        if path.exists():
            markers.append(label)
    for path in (Path('/proc/1/cgroup'), Path('/proc/self/cgroup')):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        for token in ('docker', 'containerd', 'kubepods', 'lxc', 'podman'):
            if token in text:
                markers.append(f'{path}:{token}')
    return sorted(set(markers))


def _scaling_environment() -> dict:
    import resource  # Scaling provenance uses the active POSIX runner's limits.
    clock = time.get_clock_info('process_time')
    markers = _visible_container_markers()
    affinity = None
    if hasattr(os, 'sched_getaffinity'):
        try:
            affinity = len(os.sched_getaffinity(0))
        except OSError:
            affinity = None
    return {
        'record_status': 'captured-during-scaling-run',
        'timing_data': 'scaling.csv',
        'summary_data': 'scaling.json',
        'cpu': {
            'model': _cpu_model(),
            'architecture': platform.machine() or None,
            'logical_cpus_visible': os.cpu_count(),
            'affinity_cpus_visible': affinity,
        },
        'python': {
            'implementation': platform.python_implementation(),
            'version': platform.python_version(),
        },
        'os': {
            'system': platform.system() or None,
            'release': platform.release() or None,
            'version': platform.version() or None,
        },
        'container_or_virtualization': {
            'status': 'visible-container-markers' if markers else 'no-visible-container-marker-detected',
            'visible_markers': markers,
            'limitation': 'Visible markers are recorded only; their absence does not establish bare-metal execution or exclude a hypervisor.',
        },
        'timer': {
            'name': 'time.process_time',
            'implementation': clock.implementation,
            'monotonic': clock.monotonic,
            'adjustable': clock.adjustable,
            'resolution_seconds': clock.resolution,
            'unit_in_csv': 'seconds',
        },
        'run': {
            'workers': 1,
            'repetitions_per_shape': 3,
            'address_space_limit_bytes': resource.getrlimit(resource.RLIMIT_AS)[0],
            'cpu_limit_seconds': resource.getrlimit(resource.RLIMIT_CPU)[0],
        },
        'comparability': 'These process-CPU observations are run- and environment-specific; they are not device migration latency and are not normalized for cross-machine comparison.',
    }


def baseline_masks(x):
    u=lower_closure(x.q,x.unsupported)
    t=sum(1<<i for i in range(x.n) if any(x.p[j]>>i&1 and x.lane[i]!=x.lane[j] for j in range(x.n)))
    return u,lower_closure(x.q,x.unsupported|t)


def exact(n,start,stop,out):
    ps=list(all_forward_posets(n));stop=min(stop,len(ps))
    summary=dict(suite='exact',n=n,p_start=start,p_stop=stop,posets=len(ps),instances=0,structures=0,
                 destination_traces_examined=0,feasible_cuts=0,least=0,no_least=0,aligned=0,effectively_aligned=0,
                 capability_only_unsafe=0,capability_order_unsafe=0,least_drained_events=0,
                 all_drain_events=0,oracle_mismatches=0,certificate_failures=0,independent_certificate_failures=0,
                 least_drain_histogram=[0]*(n+1))
    raw=out/f'exact-{n}-{start:02d}-{stop:02d}.csv.gz'
    with gzip.open(raw,'wt',newline='') as f:
      writer=csv.writer(f);writer.writerow(['p','q','lane_bits','capacity_0','capacity_1','unsupported','least','drain_or_left','right','feasible_count','capability_only_safe','capability_order_safe'])
      for pi in range(start,stop):
       p=ps[pi]
       for qi,q in enumerate(ps):
        if any(a&~b for a,b in zip(p,q)):continue
        for lane in itertools.product(range(2),repeat=n):
         structural,traces=structural_cuts(p,q,lane)
         summary['structures']+=1;summary['destination_traces_examined']+=traces
         aligned=all(lane[i]!=lane[j] or q[j]>>i&1 for j in range(n) for i in range(j))
         lane_bits=sum(lane[i]<<i for i in range(n))
         for cap in itertools.product(*(range(lane.count(k)+1) for k in range(2))):
          for u in range(1<<n):
           x=Instance(p,q,lane,(1,)*n,cap,u)
           feasible=feasible_from_structure(x,structural)
           if not feasible:raise AssertionError('the all-event drain must be feasible')
           meet=(1<<n)-1
           for d in feasible:meet &= d
           actual=analyze(x);isleast=meet in feasible
           if (actual['kind']=='least')!=isleast:raise AssertionError(('leastness mismatch',instance_dict(x),actual,feasible))
           if not verify_analysis(x,actual):
            summary['certificate_failures']+=1
            raise AssertionError(('certificate rejected',instance_dict(x),actual))
           if not independent_verify_analysis(x,actual):
            summary['independent_certificate_failures']+=1
            raise AssertionError(('independent certificate rejected',instance_dict(x),actual))
           if isleast:
            chosen=sum(1<<e for e in actual['cut']['drain']);right=0
            if chosen!=meet:raise AssertionError('wrong least cut')
            summary['least']+=1;summary['least_drained_events']+=chosen.bit_count()
            summary['all_drain_events']+=n;summary['least_drain_histogram'][chosen.bit_count()]+=1
           else:
            chosen=sum(1<<e for e in actual['left']);right=sum(1<<e for e in actual['right'])
            summary['no_least']+=1
           if aligned:
            fast=synthesize(x)
            if not isleast or fast['drain']!=actual['cut']['drain'] or not verify(x,fast):raise AssertionError('aligned theorem mismatch')
            summary['aligned']+=1
           if effectively_aligned(x):
            effective=synthesize_effective(x)
            if not isleast or effective['drain']!=actual['cut']['drain'] or not verify(x,effective):raise AssertionError('effective alignment theorem mismatch')
            summary['effectively_aligned']+=1
           bu,bo=baseline_masks(x);su,so=bu in feasible,bo in feasible
           summary['capability_only_unsafe']+=int(not su);summary['capability_order_unsafe']+=int(not so)
           summary['instances']+=1;summary['feasible_cuts']+=len(feasible)
           writer.writerow([pi,qi,lane_bits,*cap,u,int(isleast),chosen,right,len(feasible),int(su),int(so)])
    return summary


def weighted(out):
    cases=json.loads((ROOT/'inputs/weighted.json').read_text())
    summary=dict(suite='weighted',instances=len(cases),least=0,no_least=0,oracle_mismatches=0,
                 certificate_failures=0,independent_certificate_failures=0,destination_traces_examined=0,least_drained_units=0,total_units_least_cases=0)
    with gzip.open(out/'weighted.jsonl.gz','wt') as f:
      for case in cases:
        x=instance_from_dict(case['instance']);st,nt=structural_cuts(x.p,x.q,x.lane)
        feasible=feasible_from_structure(x,st);meet=(1<<x.n)-1
        for d in feasible:meet&=d
        actual=analyze(x);isleast=meet in feasible
        if (actual['kind']=='least')!=isleast:
            summary['oracle_mismatches']+=1
            raise AssertionError('weighted oracle leastness mismatch')
        if not verify_analysis(x,actual):
            summary['certificate_failures']+=1
            raise AssertionError('weighted production certificate failure')
        if not independent_verify_analysis(x,actual):
            summary['independent_certificate_failures']+=1
            raise AssertionError('weighted independent certificate failure')
        if isleast:
            if sum(1<<e for e in actual['cut']['drain'])!=meet:raise AssertionError('wrong weighted least cut')
            summary['least']+=1;summary['least_drained_units']+=sum(x.weight[e] for e in bits(meet))
            summary['total_units_least_cases']+=sum(x.weight)
        else:summary['no_least']+=1
        summary['destination_traces_examined']+=nt
        f.write(json.dumps({'case':case['case'],'certificate':actual,'oracle_feasible_masks':feasible},sort_keys=True)+'\n')
    return summary


def arithmetic(out):
    rows=[];total=0;roundtrips=0
    for w in range(1,7):
        count=0
        caps=[capability(mode,w) for mode in ('native','wide','split')]
        for a in range(1<<w):
          for b in range(1<<w):
            for c in range(2):
              for op in OPS:
                ref=reference_alu(op,a,b,c,w)
                for cap in caps:
                  if adapter_alu(op,a,b,c,cap)!=ref:raise AssertionError(('arithmetic mismatch',op,a,b,c,cap))
                  count+=1
              state=((a,b,c),)
              for endian in ('little','big'):
                if decode_state(encode_state(state,w,endian),1,w,endian)!=state:raise AssertionError('state roundtrip mismatch')
                roundtrips+=1
        rows.append({'width':w,'operand_carry_states':2*(1<<w)**2,'adapter_comparisons':count})
        total+=count
    boundary=0
    for w in (8,9,16):
        m=(1<<w)-1
        for a,b,c in itertools.product((0,1,m//2,m),(0,1,m//2,m),(0,1)):
          for endian in ('little','big'):
            state=((a,b,c),(b,a,1-c))
            if decode_state(encode_state(state,w,endian),2,w,endian)!=state:raise AssertionError('multibyte state mismatch')
            boundary+=1
    (out/'arithmetic-domain.json').write_text(json.dumps(rows,indent=2)+'\n')
    return dict(suite='arithmetic',widths=list(range(1,7)),operations=list(OPS),modes=['native','wide','split'],
                adapter_comparisons=total,state_roundtrips=roundtrips,multibyte_boundary_roundtrips=boundary,
                arithmetic_mismatches=0,state_mismatches=0)


def episodes(out):
    cases=json.loads((ROOT/'inputs/epochs.json').read_text())
    summary=dict(suite='episodes',epochs=len(cases),events=0,migrations=0,migrations_with_residual=0,
                 least_decisions=0,no_least_decisions=0,source_drained_events=0,destination_events=0,
                 epochs_multiple_migrations=0,step_value_mismatches=0,program_result_mismatches=0,
                 duplicate_or_missing_events=0,order_violations=0,state_roundtrip_mismatches=0,profiles={})
    with gzip.open(out/'episodes.jsonl.gz','wt') as f:
      for case in cases:
        result=run_epoch(case)
        summary['events']+=result['events'];summary['migrations']+=len(result['snapshots'])
        summary['migrations_with_residual']+=sum(bool(x['remaining']) for x in result['snapshots'])
        summary['epochs_multiple_migrations']+=int(len(result['snapshots'])>1)
        for d in result['decisions']:summary['least_decisions' if d['certificate']['kind']=='least' else 'no_least_decisions']+=1
        for e in result['trace']:summary['source_drained_events' if e['role']=='source-drain' else 'destination_events']+=1
        summary['profiles'][case['profile']]=summary['profiles'].get(case['profile'],0)+1
        f.write(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    return summary


def scaling(out):
    rows=[]
    for n in (16,32,64,128,256,512):
      for density in ('sparse','dense'):
       k=2 if density=='sparse' else 8
       p=closure(n,[(i,i+3) for i in range(n-3)]) if density=='sparse' else tuple((1<<j)-1 for j in range(n))
       q=closure(n,[(i,j) for j in range(n) for i in range(j) if p[j]>>i&1 or i%k==j%k])
       x=Instance(p,q,tuple(i%k for i in range(n)),tuple(1+i%7 for i in range(n)),(n//k,)*k,
                  sum(1<<i for i in range(n) if i%17==0))
       for rep in range(3):
        cpu=time.process_time();a=analyze(x);analysis_cpu=time.process_time()-cpu
        cpu=time.process_time();ok=verify_analysis(x,a);check_cpu=time.process_time()-cpu
        cpu=time.process_time();b=synthesize(x);fast_cpu=time.process_time()-cpu
        if not ok or a['kind']!='least' or b['drain']!=a['cut']['drain']:raise AssertionError('scaling result failure')
        rows.append(dict(n=n,density=density,lanes=k,repetition=rep,drained=len(b['drain']),
                         general_cpu_seconds=analysis_cpu,check_cpu_seconds=check_cpu,aligned_cpu_seconds=fast_cpu))
    with (out/'scaling.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (out/'scaling-environment.json').write_text(
        json.dumps(_scaling_environment(), indent=2, sort_keys=True)+'\n', encoding='utf-8'
    )
    return dict(suite='scaling',instances=12,repetitions=3,rows=len(rows),maximum_events=512,failures=0,
                timing_scope='single-worker Python structural analysis and checking; not processor migration latency')


def main():
    import resource
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',choices=['exact','weighted','arithmetic','episodes','scaling'],required=True)
    p.add_argument('--n',type=int,default=3);p.add_argument('--start',type=int,default=0);p.add_argument('--stop',type=int,default=100)
    p.add_argument('--output',type=Path,default=ROOT/'results'/'reproduced')
    args=p.parse_args()
    if args.suite=='exact' and (not 0<=args.n<=4 or args.start<0 or args.stop<=args.start):p.error('exact enumeration admits n<=4 and a nonempty P-index interval')
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    args.output.mkdir(parents=True,exist_ok=True)
    cpu=time.process_time();wall=time.perf_counter()
    if args.suite=='exact':result=exact(args.n,args.start,args.stop,args.output)
    else:result=globals()[{'weighted':'weighted','arithmetic':'arithmetic','episodes':'episodes','scaling':'scaling'}[args.suite]](args.output)
    result.update(cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    suffix=f'-{args.n}-{args.start:02d}-{min(args.stop,len(list(all_forward_posets(args.n)))):02d}' if args.suite=='exact' else ''
    path=args.output/f'{args.suite}{suffix}.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
