#!/usr/bin/env python3
"""Synchronous, bounded reproduction and deterministic scientific reconciliation."""
from __future__ import annotations
import argparse,csv,gzip,itertools,json,os,resource,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from oracle import all_forward_posets
from aggregate import aggregate
from child_diagnostics import failure_record, failure_message
METRICS={'cpu_seconds','wall_seconds','peak_rss_kib','workers'}
# Same complete exact domain; one P index per n=4 child, as in the retained run.
CHUNKS=[
    (0,0,1),(1,0,1),(2,0,2),(3,0,7),
    (4,0,1),(4,1,2),(4,2,3),(4,3,4),(4,4,5),
    (4,5,6),(4,6,7),(4,7,8),(4,8,9),(4,9,10),
    (4,10,11),(4,11,12),(4,12,13),(4,13,14),(4,14,15),
    (4,15,16),(4,16,17),(4,17,18),(4,18,19),(4,19,20),
    (4,20,21),(4,21,22),(4,22,23),(4,23,24),(4,24,25),
    (4,25,26),(4,26,27),(4,27,28),(4,28,29),(4,29,30),
    (4,30,31),(4,31,32),(4,32,33),(4,33,34),(4,34,35),
    (4,35,36),(4,36,37),(4,37,38),(4,38,39),(4,39,40),
]


def limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))


def child(arguments:list[str], *, cwd:Path=ROOT, failure_output:Path|None=None) -> dict:
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
    try:
        done=subprocess.run([sys.executable,*arguments],cwd=cwd,check=False,text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,
                            preexec_fn=limits,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    except subprocess.TimeoutExpired as exc:
        record=failure_record(arguments,None,exc.stdout,exc.stderr)
        report_failure(failure_output,record)
        raise RuntimeError(failure_message(record)) from exc
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if done.returncode:
        record=failure_record(arguments,done.returncode,done.stdout,done.stderr)
        report_failure(failure_output,record)
        raise RuntimeError(failure_message(record))
    return {'command':arguments,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
            'wall_seconds':time.perf_counter()-start,'peak_child_rss_kib':after.ru_maxrss,
            'returncode':done.returncode}


def report_failure(out:Path|None,record:dict) -> None:
    # Kept outside temporary scientific stages, including hard-killed children.
    # Append-only diagnostics never act as a completed-result/resumption marker.
    if out is None:return
    try:
        with (out/'reproduction-failures.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(record,sort_keys=True)+'\n')
    except OSError as exc:
        print('Could not retain child failure diagnostics: '+str(exc),file=sys.stderr,flush=True)


def save_measurement(out:Path,row:dict) -> None:
    # Append only actual invocations; timings are not deterministic result identifiers.
    with (out/'reproduction-invocations.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(row,sort_keys=True)+'\n')


def job(out:Path,name:str,arguments:list[str],raw_names:tuple[str,...]=()) -> None:
    summary=out/(name+'.json')
    if summary.exists():
        json.loads(summary.read_text())
        if not all((out/p).is_file() for p in raw_names):raise ValueError('incomplete existing result '+name)
        print('Retained completed chunk: '+name,flush=True);return
    with tempfile.TemporaryDirectory(prefix='.reproduce-',dir=out) as tmp:
        stage=Path(tmp)
        measured=child([*arguments,'--output',str(stage)],failure_output=out)
        if not (stage/(name+'.json')).is_file():raise ValueError('child omitted its summary')
        products=sorted(stage.iterdir())
        if any((out/p.name).exists() for p in products):raise ValueError('refusing to overwrite partial result files for '+name)
        # Publish data before the summary; a summary is the resumability marker.
        for p in products:
            if p.name!=name+'.json':p.replace(out/p.name)
        (stage/(name+'.json')).replace(summary)
        measured['task']=name
        measured['command']=[s.replace(str(stage),'<output>').replace(str(out),'<output>') for s in measured['command']]
        save_measurement(out,measured)
    print('Completed: '+name,flush=True)


def exact(out:Path,n:int,start:int,stop:int) -> None:
    count=len(list(all_forward_posets(n)))
    if not 0<=start<stop<=count:raise ValueError('P-index interval is outside the exact domain')
    for path in out.glob(f'exact-{n}-*.json'):
        prior=json.loads(path.read_text())
        if (start,stop)!=(prior['p_start'],prior['p_stop']) and max(start,prior['p_start'])<min(stop,prior['p_stop']):
            raise ValueError('new exact chunk would overlap an existing chunk')
    name=f'exact-{n}-{start:02d}-{stop:02d}'
    job(out,name,['src/experiment.py','--suite','exact','--n',str(n),'--start',str(start),'--stop',str(stop)],(name+'.csv.gz',))


def remaining(out:Path) -> None:
    for name in ('weighted','arithmetic','episodes','scaling'):
        raw={'weighted':('weighted.jsonl.gz',),'arithmetic':('arithmetic-domain.json',),
             'episodes':('episodes.jsonl.gz',),'scaling':('scaling.csv','scaling-environment.json')}[name]
        job(out,name,['src/experiment.py','--suite',name],raw)
    job(out,'weighted-exhaustive',['src/weighted_exhaustive.py'],('weighted-exhaustive-groups.csv.gz',))
    job(out,'mutations',['src/mutations.py'],('mutation-controls.json',))
    for n in range(5):
        name=f'capacity-groups-{n}'
        job(out,name,['src/capacity_audit.py','--n',str(n),'--source',str(out)],(name+'.csv.gz',))
    job(out,'weighted-obstructions',['src/capacity_audit.py','--weighted'],('weighted-obstructions.jsonl.gz',))
    measured=child(['-m','unittest','discover','-s','tests','-v'],failure_output=out);measured['task']='unit-tests';save_measurement(out,measured)
    with tempfile.TemporaryDirectory(prefix='.interface-',dir=out) as tmp:
        cert=Path(tmp)/'certificate.json'
        for args in (['src/cli.py','analyze','inputs/example.json','--output',str(cert)],
                     ['src/cli.py','check','inputs/example.json','--certificate',str(cert)],
                     ['src/cli.py','robust','inputs/example.json']):
            measured=child(args,failure_output=out);measured['task']='documented-interface'
            measured['command']=[s.replace(str(cert),'<temporary-certificate>') for s in measured['command']]
            save_measurement(out,measured)
    print('Unit tests and all documented interface commands passed.',flush=True)


def exact_rows(folder:Path,n:int):
    chunks=sorted((json.loads(p.read_text()) for p in folder.glob(f'exact-{n}-*.json')),key=lambda x:x['p_start'])
    for c in chunks:
        p=folder/f"exact-{n}-{c['p_start']:02d}-{c['p_stop']:02d}.csv.gz"
        with gzip.open(p,'rt',newline='') as f:yield from csv.DictReader(f)


def scaling_environment_status(path:Path) -> str:
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('timing_data')!='scaling.csv':
        raise ValueError('scaling environment record is not linked to scaling.csv')
    timer=data.get('timer')
    if type(timer) is not dict or timer.get('name')!='time.process_time' or timer.get('unit_in_csv')!='seconds':
        raise ValueError('scaling environment record has an incompatible timer declaration')
    status=data.get('record_status')
    if type(status) is not str or not status:
        raise ValueError('scaling environment record lacks provenance status')
    return status


def reconcile(out:Path) -> None:
    canonical=ROOT/'results/campaign'
    observed=aggregate(out,out/'summary');expected=json.loads((ROOT/'results/summary/summary.json').read_text())
    if {k:v for k,v in observed.items() if k!='scaling_median_ms'}!={k:v for k,v in expected.items() if k!='scaling_median_ms'}:
        raise ValueError('scientific summary mismatch against retained campaign')
    counts=[]
    sentinel=object()
    for n in range(5):
        count=0
        for a,b in itertools.zip_longest(exact_rows(canonical,n),exact_rows(out,n),fillvalue=sentinel):
            if a!=b:raise ValueError('exact raw row differs at n='+str(n)+' row='+str(count))
            count+=1
        counts.append(count)
    compared=[]
    for p in sorted(canonical.glob('*.gz')):
        if p.name.startswith('exact-'):continue
        q=out/p.name
        with gzip.open(p,'rb') as a,gzip.open(q,'rb') as b:
            while True:
                x,y=a.read(1024*1024),b.read(1024*1024)
                if x!=y:raise ValueError('decompressed scientific data mismatch: '+p.name)
                if not x:break
        compared.append(p.name)
    for name in ('arithmetic-domain.json','mutation-controls.json'):
        if json.loads((canonical/name).read_text())!=json.loads((out/name).read_text()):raise ValueError('deterministic JSON mismatch: '+name)
        compared.append(name)
    with (canonical/'scaling.csv').open(newline='') as a,(out/'scaling.csv').open(newline='') as b:
        def stable(rows):return [{k:v for k,v in r.items() if not k.endswith('_seconds')} for r in csv.DictReader(rows)]
        if stable(a)!=stable(b):raise ValueError('scaling shape or correctness mismatch')
    retained_environment=scaling_environment_status(canonical/'scaling-environment.json')
    reproduced_environment=scaling_environment_status(out/'scaling-environment.json')
    result={'scientific_summaries_equal':True,'exact_rows_compared_by_n':counts,'exact_rows_equal':True,
            'other_deterministic_files_equal':compared,'scaling_non_timing_fields_equal':True,
            'scaling_environment_records_present':True,
            'retained_scaling_environment_status':retained_environment,
            'reproduced_scaling_environment_status':reproduced_environment,
            'timing_comparison':'Not required: CPU, wall time, RSS and timing medians are machine observations.',
            'scope':'Clean local executable reproduction, not an independent mathematical proof or hardware validation.'}
    (out/'reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'results/reproduced')
    p.add_argument('--task',choices=('all','exact','remaining','reconcile'),default='all')
    p.add_argument('--n',type=int,choices=range(5));p.add_argument('--start',type=int,default=0);p.add_argument('--stop',type=int)
    a=p.parse_args();out=a.output.resolve()
    protected=[(ROOT/s).resolve() for s in ('src','tests','inputs','proofs','results/campaign','results/summary')]
    if out==ROOT or any(out==d or d in out.parents or out in d.parents for d in protected):p.error('output would collide with retained project inputs or results')
    out.mkdir(parents=True,exist_ok=True)
    try:
        if a.task=='exact':
            if a.n is None:p.error('--n is required for --task exact')
            exact(out,a.n,a.start,a.stop if a.stop is not None else len(list(all_forward_posets(a.n))))
        else:
            if a.n is not None or a.stop is not None or a.start:p.error('exact interval arguments require --task exact')
            if a.task=='all':
                for n,start,stop in CHUNKS:exact(out,n,start,stop)
            if a.task in ('all','remaining'):remaining(out)
            if a.task in ('all','reconcile'):
                before=resource.getrusage(resource.RUSAGE_SELF);wall=time.perf_counter()
                reconcile(out)
                after=resource.getrusage(resource.RUSAGE_SELF)
                save_measurement(out,{'task':'reconciliation','cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                                     'wall_seconds':time.perf_counter()-wall,'peak_rss_kib':after.ru_maxrss,'returncode':0})
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,AssertionError) as exc:
        print('Reproduction stopped: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
