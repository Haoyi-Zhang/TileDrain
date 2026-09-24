"""Benign event-machine validation of accepted sealed-epoch migrations.

Ownership transfer is one abstract atomic transition, not a distributed
protocol. A reference interpreter checks every visible completion; it is never
used to compute the adapter result. Raw traces retain all original identities.
"""
from __future__ import annotations
from dataclasses import asdict
from contracts import Instance, closure, safe
from general import analyze, verify_analysis
from semantics import Event, capability, dependence_order, adapter_step, reference_step, encode_state, decode_state
from inputs import instance_dict


class Machine:
    def __init__(self, state, events, p, w, lanes, caps):
        self.state = tuple(tuple(row) for row in state)
        self.reference = self.state
        self.events = tuple(events)
        self.p = p
        self.w = w
        self.lanes = list(lanes)
        self.caps = list(caps)
        self.owner = 0
        self.done = set()
        self.trace = []
        self.snapshots = []

    def commit(self, owner: int, event: int, role: str) -> None:
        if type(owner) is not int or owner != self.owner:
            raise PermissionError('only the unique current owner may commit')
        if event in self.done or not 0 <= event < len(self.events):
            raise ValueError('event already completed or outside this epoch')
        if any(self.p[event] >> i & 1 and i not in self.done for i in range(len(self.events))):
            raise ValueError('architectural predecessor still pending')
        if any(i < event and i not in self.done and self.lanes[i] == self.lanes[event]
               for i in range(len(self.events))):
            raise ValueError('source/destination FIFO predecessor still pending')
        next_state, observation = adapter_step(self.state,self.events[event],self.caps[self.lanes[event]])
        expected_state, expected_observation = reference_step(self.reference,self.events[event],self.w)
        if next_state != expected_state or observation != expected_observation:
            raise AssertionError('adapter and independently interpreted step disagree')
        self.state, self.reference = next_state, expected_state
        self.done.add(event)
        self.trace.append({'event':event,'role':role,'owner':owner,'observation':list(observation),
                           'state':[list(row) for row in self.state]})

    def transfer(self, lanes, caps, endian: str) -> None:
        for cap in caps:
            cap.validate()
            if cap.width != self.w:
                raise ValueError('width mismatch in target state contract')
        for i,e in enumerate(self.events):
            if i not in self.done and e.opcode not in caps[lanes[i]].operations:
                raise ValueError('unsupported operation would remain at destination')
        payload = encode_state(self.state,self.w,endian)
        received = decode_state(payload,len(self.state),self.w,endian)
        if received != self.state:
            raise AssertionError('canonical state changed during transfer')
        old_owner = self.owner
        # Model assumption: this ownership replacement is atomic. No fault or
        # concurrent external side effect occurs during it.
        self.owner = old_owner+1
        self.state = received
        self.lanes, self.caps = list(lanes), list(caps)
        self.snapshots.append({'old_owner':old_owner,'new_owner':self.owner,'endian':endian,
                               'payload_hex':payload.hex(),'completed':sorted(self.done),
                               'remaining':[i for i in range(len(self.events)) if i not in self.done]})


def run_epoch(case: dict) -> dict:
    events=tuple(Event(**e) for e in case['events'])
    n,w,contexts=len(events),case['width'],case['contexts']
    p=dependence_order(events)
    m=Machine(case['initial'],events,p,w,case['source_lane'],[capability('native',w)]*contexts)
    input_order_state=m.state; input_order_observations={}
    for event in events:
        input_order_state, obs=reference_step(input_order_state,event,w)
        input_order_observations[event.identity]=obs
    decisions=[]
    priority={event:rank for rank,event in enumerate(case['priority'])}
    for proposal in case['moves']:
        pending=[e for e in range(n) if e not in m.done]
        if not pending:
            break
        local={event:i for i,event in enumerate(pending)}
        pp=closure(len(pending),[(local[i],local[j]) for j in pending for i in pending if p[j]>>i&1])
        qq=closure(len(pending),[(i,j) for j in range(len(pending)) for i in range(j)
                                if pp[j]>>i&1 or m.lanes[pending[i]]==m.lanes[pending[j]]])
        target_caps=[capability(t['mode'],w,tuple(t['operations']),proposal['endian']) for t in proposal['tile']]
        lanes=tuple(proposal['lane'][e] for e in pending)
        u=sum(1<<i for i,e in enumerate(pending) if events[e].opcode not in target_caps[lanes[i]].operations)
        x=Instance(pp,qq,lanes,tuple(case['weight'][e] for e in pending),tuple(proposal['capacity']),u)
        cert=analyze(x)
        if not verify_analysis(x,cert):
            raise AssertionError('generated decision certificate was rejected')
        drain=cert['cut']['drain'] if cert['kind']=='least' else cert['left']
        if not safe(x,sum(1<<e for e in drain)):
            raise AssertionError('chosen migration cut is unsafe')
        selected=[pending[i] for i in drain]
        decisions.append({'pending':pending,'instance':instance_dict(x),'certificate':cert,
                          'selected_original_events':selected,'selection':'least' if cert['kind']=='least' else 'feasible-left-witness'})
        for e in selected:
            m.commit(m.owner,e,'source-drain')
        m.transfer(proposal['lane'],target_caps,proposal['endian'])
        pending=[e for e in range(n) if e not in m.done]
        if pending:
            heads=[e for e in pending if not any(i<e and m.lanes[i]==m.lanes[e] for i in pending)]
            chosen=min(heads,key=priority.get)
            m.commit(m.owner,chosen,'destination')
    while len(m.done)<n:
        pending=[e for e in range(n) if e not in m.done]
        heads=[e for e in pending if not any(i<e and m.lanes[i]==m.lanes[e] for i in pending)]
        m.commit(m.owner,min(heads,key=priority.get),'destination')
    if m.state != input_order_state:
        raise AssertionError('conservative dependency order failed to preserve final program state')
    if any(tuple(row['observation']) != input_order_observations[row['event']] for row in m.trace):
        raise AssertionError('per-event result differs from input-order program result')
    if len(m.trace)!=n or {row['event'] for row in m.trace}!=set(range(n)):
        raise AssertionError('missing or duplicate completion')
    return {'case':case['case'],'width':w,'profile':case['profile'],'events':n,'p':list(p),
            'initial':case['initial'],'decisions':decisions,'snapshots':m.snapshots,'trace':m.trace,
            'final':[list(row) for row in m.state],'reference_program_final':[list(row) for row in input_order_state]}
