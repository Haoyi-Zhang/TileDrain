"""Read the manuscript's source-bound structural checking measurements."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
METRICS=('general_cpu_seconds','check_cpu_seconds','aligned_cpu_seconds')
SHAPES={'sparse':2,'dense':8}
SIZES=(16,32,64,128,256,512)
FILES=('scaling.csv','scaling.json','scaling-environment.json')
COLUMNS=('n','density','lanes','repetition','drained',*METRICS)


def file_digest(path:Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_rows(rows:list[dict]) -> list[dict]:
    expected={(n,shape,rep) for n in SIZES for shape in SHAPES for rep in range(3)}
    seen=set();values={}
    for row in rows:
        if set(row)!={'n','density','lanes','repetition','drained',*METRICS}:
            raise ValueError('unexpected scaling columns')
        n,shape,rep=int(row['n']),row['density'],int(row['repetition'])
        key=n,shape,rep
        if key not in expected or key in seen or int(row['lanes'])!=SHAPES[shape]:
            raise ValueError('scaling cell missing, duplicated or outside the declared shapes')
        seen.add(key)
        if not 0<=int(row['drained'])<=n:raise ValueError('invalid drain count')
        for metric in METRICS:
            value=float(row[metric])
            if not math.isfinite(value) or value<0:raise ValueError('CPU interval must be finite and nonnegative')
            values.setdefault((n,shape,metric),[]).append(value*1000)
    if seen!=expected:raise ValueError('incomplete 36-row scaling domain')
    result=[]
    for n in SIZES:
        for shape in SHAPES:
            selected=[r for r in rows if int(r['n'])==n and r['density']==shape]
            if len({int(r['drained']) for r in selected})!=1:raise ValueError('repetitions disagree on structural outcome')
            cell={'n':n,'density':shape,'lanes':SHAPES[shape],'repetitions':3}
            for metric in METRICS:
                xs=values[n,shape,metric]
                cell[metric]={'median_ms':statistics.median(xs),'min_ms':min(xs),'max_ms':max(xs),'zero_intervals':sum(v==0 for v in xs)}
            result.append(cell)
    return result


def read_bundle(folder:Path, *, require_captured:bool=False) -> dict:
    environment=json.loads((folder/'scaling-environment.json').read_text(encoding='utf-8'))
    status=environment.get('record_status')
    if status not in {'captured-during-scaling-run','retrospective-partial-from-retained-materials'} or (require_captured and status!='captured-during-scaling-run'):
        raise ValueError('incompatible measurement provenance status')
    if environment.get('timing_data')!='scaling.csv':raise ValueError('measurement links do not resolve to the selected batch')
    if environment['timer']['name']!='time.process_time' or environment['timer']['unit_in_csv']!='seconds':raise ValueError('incompatible timing boundary')
    if status=='captured-during-scaling-run':
        if environment.get('summary_data')!='scaling.json':raise ValueError('measurement links do not resolve to the selected batch')
        if any(not environment.get(section,{}).get(field) for section,field in (('cpu','model'),('cpu','architecture'),('python','implementation'),('python','version'),('os','system'),('os','release'))):
            raise ValueError('selected runtime identity is incomplete')
        if environment.get('run')!={'address_space_limit_bytes':3*1024**3,'cpu_limit_seconds':40,'repetitions_per_shape':3,'workers':1}:raise ValueError('selected run limits differ')
    else:
        historical=environment.get('historical_environment',{})
        if not historical or any(v!='unknown-not-recorded' for v in historical.values()):raise ValueError('historical identity must stay explicitly unrecorded')
    summary=json.loads((folder/'scaling.json').read_text(encoding='utf-8'))
    expected={'suite':'scaling','instances':12,'repetitions':3,'rows':36,'maximum_events':512,'failures':0,'workers':1}
    if any(type(summary.get(k)) is not type(v) or summary[k]!=v for k,v in expected.items()):raise ValueError('selected scaling summary differs')
    with (folder/'scaling.csv').open(newline='',encoding='utf-8') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=list(COLUMNS):raise ValueError('unexpected or duplicated scaling header')
        rows=list(reader)
    cells=summarize_rows(rows)
    return {'rows':36,'cells':cells,'zero_intervals':sum(c[m]['zero_intervals'] for c in cells for m in METRICS),
            'environment':environment,'suite_summary':summary,
            'non_timing_rows':[{k:r[k] for k in COLUMNS if k not in METRICS} for r in rows],
            'timing_scope':'Single-call process CPU intervals for three structural procedures; instance construction, source execution and transfer excluded. API resolution is not effective measurement precision; zero observations are retained and no timing ratio is computed.'}


def load_report(folder:Path|None=None, *, artifact_root:Path=ROOT) -> dict:
    folder=folder or artifact_root/'results/scaling'
    provenance=json.loads((folder/'provenance.json').read_text(encoding='utf-8'))
    if set(provenance['files'])!=set(FILES):raise ValueError('selected measurement files differ')
    for name in FILES:
        if file_digest(folder/name)!=provenance['files'][name]:raise ValueError('measurement file identity mismatch: '+name)
    required={'src/experiment.py','src/contracts.py','src/general.py','src/robust.py'}
    bound={r['path'] for r in provenance['source_files']}
    if bound!=required or len(bound)!=len(provenance['source_files']):raise ValueError('incomplete timed-source binding')
    for source in provenance['source_files']:
        rel=Path(source['path']);path=(artifact_root/rel).resolve()
        if rel.is_absolute() or '..' in rel.parts or not path.is_relative_to(artifact_root.resolve()):raise ValueError('source path leaves artifact')
        if file_digest(path)!=source['sha256']:raise ValueError('scientific source differs from the measured source: '+source['path'])
    return {**read_bundle(folder,require_captured=True),'source_commit':provenance['source_commit'],'workflow_run_id':provenance['workflow_run_id']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'results/scaling')
    args=parser.parse_args()
    print(json.dumps(load_report(args.source),indent=2))
