"""Declared benign negative controls and malformed-packet tests.

Each row is a named hand-constructed fault, not a claim of complete mutation
coverage. No third-party system, exploit or real device is involved.
"""
from __future__ import annotations
import json,time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from contracts import Instance,closure,synthesize,verify,MAX_INTEGER
from general import analyze,verify_analysis
from independent import independent_verify_analysis
from inputs import instance_dict
from semantics import Event,capability,reference_alu,encode_state,decode_state,reference_step
from simulator import Machine


def run_controls() -> list[dict]:
    rows=[]
    def reject(name,x,cert,mechanism):
        actual=verify_analysis(x,cert)
        independent=independent_verify_analysis(x,cert)
        if actual or independent:raise AssertionError('bad certificate accepted: '+name)
        rows.append(dict(control=name,expected='reject',actual='reject',mechanism=mechanism,
                         instance=instance_dict(x),mutated_certificate=cert))
    def rejects_exception(name,fn,mechanism):
        try:fn()
        except (ValueError,PermissionError,TypeError):
            rows.append(dict(control=name,expected='reject',actual='reject',mechanism=mechanism))
        else:raise AssertionError('invalid object was not rejected: '+name)

    order=Instance((0,1),(0,1),(0,1),(1,1),(1,1),0)
    empty={'kind':'least','cut':{'drain':[],'necessity':[]}}
    reject('missing-order',order,empty,'residual FIFO interleaving [1,0] violates P')
    unsupported=Instance((0,),(0,),(0,),(1,),(1,),1)
    reject('unsupported-operation',unsupported,empty,'unsupported operation would remain')
    capacity=Instance((0,0),(0,1),(0,0),(1,1),(1,),0)
    reject('missing-capacity-drain',capacity,empty,'two residual units exceed one-unit queue')
    nonideal=Instance((0,0),(0,1),(0,1),(1,1),(1,1),2)
    reject('nonideal-source-prefix',nonideal,{'kind':'least','cut':{'drain':[1],'necessity':[{'event':1,'root':1,'kind':'unsupported'}]}},'source predecessor zero is omitted')
    optional=Instance((0,),(0,),(0,),(1,),(1,),0)
    reject('forged-necessity',optional,{'kind':'least','cut':{'drain':[0],'necessity':[{'event':0,'root':0,'kind':'unsupported'}]}},'cut is safe but its extra event is not mandatory')
    nonleast=Instance((0,0),(0,0),(0,0),(1,1),(1,),0)
    reject('unaligned-suffix-reason',nonleast,{'kind':'least','cut':{'drain':[0],'necessity':[{'event':0,'root':0,'kind':'capacity'}]}},'a destination suffix is not forced by Q')
    reject('forged-no-least-meet',nonleast,{'kind':'no_least','left':[0],'right':[0]},'claimed witness intersection is feasible')
    reject('duplicate-drain-id',unsupported,{'kind':'least','cut':{'drain':[0,0],'necessity':[]}},'duplicate identity is not a set encoding')
    good=analyze(order);bad=deepcopy(good);bad['cut']['necessity'][0]['later']=0
    reject('invalid-order-witness',order,bad,'self-pair cannot justify an earlier endpoint')
    for name,x in [
      ('negative-size',replace(optional,weight=(-1,))),
      ('boolean-mask',replace(optional,unsupported=True)),
      ('out-of-range-lane',replace(optional,lane=(1,))),
      ('unsupported-mask-overflow',replace(optional,unsupported=2)),
      ('nontransitive-source-order',Instance((0,0,0),(0,1,2),(0,1,2),(1,1,1),(1,1,1))),
      ('source-omits-virtual-edge',replace(order,q=(0,0)))
    ]:reject(name,x,empty,'input grammar admission')

    large=Instance((0,0),(0,1),(0,0),(MAX_INTEGER,MAX_INTEGER),(MAX_INTEGER,),0)
    large_cert=analyze(large)
    if not verify_analysis(large,large_cert) or not independent_verify_analysis(large,large_cert) or large_cert['cut']['drain']!=[0]:raise AssertionError('large integer arithmetic wrapped')
    rows.append(dict(control='nonwrapping-capacity-sum',expected='accept-exact',actual='accept-exact',
                     total_size=2*MAX_INTEGER,certificate=large_cert))
    for name,actual in [('physical-width-carry',(0,0)),('saturating-add',(15,1))]:
        expected=reference_alu('ADD',15,1,0,4)
        if actual==expected:raise AssertionError('negative arithmetic mutant survived')
        rows.append(dict(control=name,expected='mismatch',actual='mismatch',operands=[15,1,0],width=4,
                         reference=list(expected),mutant=list(actual)))
    state=((0,0,1),);lost=((0,0,0),);event=Event(0,0,'ADC',0,None,0)
    _,good_obs=reference_step(state,event,4);_,bad_obs=reference_step(lost,event,4)
    if good_obs==bad_obs:raise AssertionError('lost carry was unobservable')
    rows.append(dict(control='lost-carry-state',expected='mismatch',actual='mismatch',
                     reference=list(good_obs),mutant=list(bad_obs),empty_epoch_does_not_repair=True))
    state=((0x0102,0x0304,1),);payload=encode_state(state,16,'little')
    wrong=decode_state(payload,1,16,'big')
    if wrong==state:raise AssertionError('wrong endian state unexpectedly equal')
    rows.append(dict(control='wrong-endian-state',expected='mismatch',actual='mismatch',
                     encoded_byte_order='little',mutant_decode_byte_order='big',payload_hex=payload.hex(),
                     original=[list(r) for r in state],mutant=[list(r) for r in wrong]))
    rejects_exception('truncated-state',lambda:decode_state(b'\x00\x00',1,4,'little'),'exact length')
    rejects_exception('extra-state-byte',lambda:decode_state(b'\x00'*4,1,4,'little'),'exact length')
    rejects_exception('non-bit-carry',lambda:decode_state(b'\x00\x00\x02',1,4,'little'),'carry range')
    rejects_exception('unused-high-state-bits',lambda:decode_state(b'\x00\xff\x00\x00\x00',1,9,'little'),'virtual width admission')
    rejects_exception('missing-carry-storage',lambda:replace(capability('native',4),carry_storage=False).validate(),'global state contract, not opcode cut')
    rejects_exception('insufficient-wide-helper',lambda:replace(capability('wide',4),physical_width=4).validate(),'physical sum must fit')
    rejects_exception('unknown-adapter',lambda:replace(capability('native',4),mode='unproved').validate(),'finite template grammar')
    rejects_exception('duplicate-opcode-capability',lambda:replace(capability('native',4),operations=('ADD','ADD')).validate(),'exact operation descriptor')
    e=Event(0,0,'COPY',0,None,1);cap=capability('native',4)
    m=Machine(((0,0,0),),(e,),(0,),4,[0],[cap]);m.transfer([0],[cap],'little')
    rejects_exception('stale-completion-authority',lambda:m.commit(0,0,'destination'),'donor cannot commit after abstract atomic transfer')
    m.commit(m.owner,0,'destination')
    rejects_exception('duplicate-completion',lambda:m.commit(m.owner,0,'destination'),'pending identity guard')
    m=Machine(((0,0,0),),(e,),(0,),4,[0],[cap])
    for _ in range(8):m.transfer([0],[cap],'little')
    if m.trace or m.done:raise AssertionError('migration unexpectedly completed an event')
    rows.append(dict(control='migration-only-nonprogress',expected='safe-no-progress',actual='safe-no-progress',
                     accepted_transfers=8,completions=0,pending=[0],scope='finite prefix of indefinitely repeatable silent transfer'))
    return rows


if __name__=='__main__':
    import argparse
    import resource  # POSIX limits belong to the runner, not the portable controls.
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    cpu=time.process_time();wall=time.perf_counter();rows=run_controls();args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'mutation-controls.json').write_text(json.dumps(rows,indent=2)+'\n')
    result=dict(suite='mutations',controls=len(rows),unexpected_outcomes=0,
                cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    (args.output/'mutations.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
