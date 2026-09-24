"""Bounded JSON interface for structural cut analysis and certificate checking."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from inputs import instance_from_dict
from general import analyze,verify_analysis
from robust import effectively_aligned,obstruction_capacity,synthesize_effective

MAX_FILE_BYTES=1024*1024

def unique_object(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate JSON object field: '+k)
        result[k]=v
    return result

def read_json(path: Path):
    with path.open('rb') as f:data=f.read(MAX_FILE_BYTES+1)
    if len(data)>MAX_FILE_BYTES:raise ValueError('JSON input exceeds the one-MiB interface bound')
    return json.loads(data.decode('utf-8'),object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('analyze','check','robust'))
    parser.add_argument('instance',type=Path)
    parser.add_argument('--certificate',type=Path)
    parser.add_argument('--output',type=Path)
    a=parser.parse_args()
    if (a.command=='check') != (a.certificate is not None):parser.error('--certificate is required only for check')
    try:
        x=instance_from_dict(read_json(a.instance))
        if a.command=='analyze':result=analyze(x)
        elif a.command=='check':
            accepted=verify_analysis(x,read_json(a.certificate));result={'accepted':accepted}
            if not accepted:
                print(json.dumps(result));return 1
        else:
            ea=effectively_aligned(x)
            result={'effectively_aligned':ea,'mathematical_capacity_robustness':ea,
                    'scope':'fixed orders, lane assignment, unsupported set and positive sizes; all nonnegative integer capacities'}
            if ea:result['cut_at_current_capacity']=synthesize_effective(x)
            else:
                try: result['no_least_capacity']=list(obstruction_capacity(x))
                except ValueError:
                    result['no_least_capacity']=None
                    result['encoder_hold']='The mathematical obstruction exceeds an encoded capacity. Necessity over the truncated capacity range is not claimed.'
        text=json.dumps(result,indent=2)+'\n'
        if a.output:
            # Do not silently overwrite an existing certificate or input.
            with a.output.open('x',encoding='utf-8') as f:f.write(text)
        else:print(text,end='')
        return 0
    except (OSError,UnicodeError,ValueError,TypeError,RecursionError) as exc:
        print('error: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
