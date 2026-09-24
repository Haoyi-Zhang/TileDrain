"""Deterministic generation of exact, self-contained scientific inputs.

Generated JSON is retained in inputs/; reproduction reads those exact bytes.
No fetched benchmark or external dataset is used.
"""
from __future__ import annotations
import json
import random
from dataclasses import asdict
from pathlib import Path
from contracts import Instance, closure
from semantics import OPS, Event


def instance_dict(x: Instance) -> dict:
    return dict(p=list(x.p), q=list(x.q), lane=list(x.lane), weight=list(x.weight),
                capacity=list(x.capacity), unsupported=x.unsupported)


def instance_from_dict(data: dict) -> Instance:
    if type(data) is not dict or set(data) != {'p','q','lane','weight','capacity','unsupported'}:
        raise ValueError('instance fields do not match the finite grammar')
    if any(type(data[k]) is not list or len(data[k]) > 512 for k in ('p','q','lane','weight','capacity')):
        raise ValueError('instance vectors must be bounded lists')
    x = Instance(*(tuple(data[k]) for k in ('p','q','lane','weight','capacity')), data['unsupported'])
    x.validate(aligned=False)
    return x


def weighted_inputs() -> list[dict]:
    rng = random.Random(271828)
    cases = []
    for index in range(512):
        n, k = 5, 2 + index % 2
        edges = [(i,j) for j in range(n) for i in range(j) if rng.randrange(4) == 0]
        p = closure(n, edges)
        q = closure(n, edges + [(i,j) for j in range(n) for i in range(j) if rng.randrange(5) == 0])
        lane = tuple(rng.randrange(k) for _ in range(n))
        weight = tuple(rng.randrange(1,8) for _ in range(n))
        capacity = tuple(rng.randrange(1+sum(weight[i] for i in range(n) if lane[i]==l)) for l in range(k))
        x = Instance(p,q,lane,weight,capacity,rng.randrange(1<<n))
        cases.append({'case':f'weighted-{index:04d}','instance':instance_dict(x)})
    return cases


def epoch_inputs() -> list[dict]:
    rng = random.Random(314159)
    cases = []
    for index in range(256):
        w, n, contexts = rng.randrange(2,9), rng.randrange(8,25), 2 + index % 2
        events = []
        for e in range(n):
            events.append(Event(e,rng.randrange(contexts),OPS[rng.randrange(4)],rng.randrange(2),
                                rng.randrange(2) if rng.randrange(2) else None,rng.randrange(1<<w)))
        initial = [[rng.randrange(1<<w),rng.randrange(1<<w),rng.randrange(2)] for _ in range(contexts)]
        weights = [rng.randrange(1,8) for _ in range(n)]
        preserve = index % 2 == 0
        moves = []
        for move in range(3):
            lanes = [event.context if preserve else rng.randrange(contexts) for event in events]
            totals = [sum(weights[e] for e in range(n) if lanes[e]==l) for l in range(contexts)]
            capacities = totals if preserve else [rng.randrange(total+1) for total in totals]
            lane_caps = []
            for lane in range(contexts):
                allowed = list(OPS) if preserve else [op for op in OPS if rng.randrange(5) != 0]
                lane_caps.append({'mode':('native','wide','split')[(index+move+lane)%3],
                                  'operations':allowed})
            moves.append({'lane':lanes,'capacity':capacities,'tile':lane_caps,
                          'endian':'little' if move%2==0 else 'big'})
        priority = list(range(n)); rng.shuffle(priority)
        cases.append(dict(case=f'epoch-{index:04d}',width=w,contexts=contexts,
                          initial=initial,events=[asdict(e) for e in events],weight=weights,
                          source_lane=[e.context for e in events],priority=priority,moves=moves,
                          profile='preserved-lanes' if preserve else 'changed-lanes'))
    return cases


def write_inputs(directory: Path) -> None:
    directory.mkdir(parents=True,exist_ok=True)
    for filename, value in (('weighted.json',weighted_inputs()),('epochs.json',epoch_inputs())):
        path = directory / filename
        text = json.dumps(value,sort_keys=True,separators=(',',':'))+'\n'
        if path.exists() and path.read_text() != text:
            raise ValueError('refusing to overwrite different frozen input: '+filename)
        path.write_text(text)
    example = Instance(closure(6,[(0,2),(1,3),(2,4)]),closure(6,[(0,2),(1,3),(2,4),(0,1),(2,3),(4,5)]),
                       (0,0,1,1,0,0),(1,1,1,1,1,1),(2,2),1<<3)
    (directory/'example.json').write_text(json.dumps(instance_dict(example),indent=2)+'\n')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'inputs')
    args=parser.parse_args(); write_inputs(args.output)
