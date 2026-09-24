"""Small canonical integer machine and three declared arithmetic adapters.

No native machine ISA, hardware timing, device or external service is modeled.
All intermediate arithmetic uses exact Python integers. The independently
written reference interpreter is not called by the adapter implementation.
"""
from __future__ import annotations
from dataclasses import dataclass
from contracts import closure

OPS = ('COPY', 'XOR', 'ADD', 'ADC')
MAX_WIDTH = 16
State = tuple[tuple[int, int, int], ...]  # two registers and one carry per context


def _width(w: int) -> None:
    if type(w) is not int or not 1 <= w <= MAX_WIDTH:
        raise ValueError('virtual width outside the finite adapter grammar')


def _operands(a: int, b: int, c: int, w: int) -> None:
    _width(w)
    if any(type(v) is not int or not 0 <= v < 2**w for v in (a, b)):
        raise ValueError('register value outside the virtual width')
    if type(c) is not int or c not in (0, 1):
        raise ValueError('carry must be a bit')


@dataclass(frozen=True)
class Capability:
    mode: str
    width: int
    physical_width: int
    limb_bits: int
    operations: tuple[str, ...] = OPS
    endian: str = 'little'
    carry_storage: bool = True

    def validate(self) -> None:
        _width(self.width)
        if self.mode not in ('native', 'wide', 'split'):
            raise ValueError('unknown implementation template')
        if type(self.physical_width) is not int or type(self.limb_bits) is not int:
            raise ValueError('width fields must be integers')
        if self.mode == 'native' and (self.physical_width != self.width or self.limb_bits != 0):
            raise ValueError('native template has precisely the virtual width')
        if self.mode == 'wide' and (not self.width + 1 <= self.physical_width <= 32 or self.limb_bits != 0):
            raise ValueError('widened sum must fit without physical overflow')
        if self.mode == 'split' and (not 1 <= self.limb_bits <= self.width or
                                     self.physical_width != max(self.limb_bits, self.width-self.limb_bits)+1):
            raise ValueError('split helper words must include local carry space')
        if type(self.operations) is not tuple or len(self.operations) > len(OPS):
            raise ValueError('operations must be a bounded tuple')
        if any(type(op) is not str or op not in OPS for op in self.operations) or len(set(self.operations)) != len(self.operations):
            raise ValueError('invalid or duplicate operation capability')
        if self.endian not in ('little', 'big') or self.carry_storage is not True:
            raise ValueError('canonical state needs explicit endianness and carry storage')


def capability(mode: str, w: int, operations: tuple[str, ...] = OPS, endian: str = 'little') -> Capability:
    _width(w)
    limb = (w + 1) // 2
    c = Capability(mode, w, w if mode == 'native' else (2*w if mode == 'wide' else max(limb,w-limb)+1),
                   limb if mode == 'split' else 0, operations, endian)
    c.validate()
    return c


def reference_alu(op: str, a: int, b: int, c: int, w: int) -> tuple[int, int]:
    _operands(a, b, c, w)
    if op == 'COPY':
        return b, c
    if op == 'XOR':
        return a ^ b, c
    if op not in ('ADD', 'ADC'):
        raise ValueError('unknown virtual opcode')
    quotient, remainder = divmod(a + b + (c if op == 'ADC' else 0), 2**w)
    return remainder, quotient


def adapter_alu(op: str, a: int, b: int, carry: int, cap: Capability) -> tuple[int, int]:
    cap.validate()
    _operands(a, b, carry, cap.width)
    if op not in cap.operations:
        raise ValueError('operation has no declared adapter')
    w = cap.width
    mask = (1 << w) - 1
    if cap.mode == 'split':
        z = cap.limb_bits
        lo_mask, hi_mask = (1 << z) - 1, (1 << (w-z)) - 1
        al, ah, bl, bh = a & lo_mask, a >> z, b & lo_mask, b >> z
        if op == 'COPY':
            return (bh << z) | bl, carry
        if op == 'XOR':
            return ((ah ^ bh) << z) | (al ^ bl), carry
        low_sum = al + bl + (carry if op == 'ADC' else 0)
        low_out, low_carry = low_sum & lo_mask, low_sum >> z
        high_sum = ah + bh + low_carry
        high_out, high_carry = high_sum & hi_mask, high_sum >> (w-z)
        return (high_out << z) | low_out, high_carry
    if op == 'COPY':
        return b, carry
    if op == 'XOR':
        return a ^ b, carry
    total = a + b + (carry if op == 'ADC' else 0)
    if cap.mode == 'wide':
        physical_sum = total & ((1 << cap.physical_width) - 1)
        return physical_sum & mask, (physical_sum >> w) & 1
    return total & mask, 1 if total > mask else 0


def validate_state(state: State, w: int) -> None:
    _width(w)
    if type(state) is not tuple or not 1 <= len(state) <= 16:
        raise ValueError('one to sixteen canonical contexts are required')
    for row in state:
        if type(row) is not tuple or len(row) != 3:
            raise ValueError('canonical context has two registers and carry')
        _operands(*row, w)


def encode_state(state: State, w: int, endian: str) -> bytes:
    validate_state(state, w)
    if endian not in ('little', 'big'):
        raise ValueError('explicit byte order is required')
    size = (w + 7) // 8
    return b''.join(a.to_bytes(size, endian) + b.to_bytes(size, endian) + bytes((c,))
                    for a, b, c in state)


def decode_state(payload: bytes, contexts: int, w: int, endian: str) -> State:
    _width(w)
    if type(contexts) is not int or not 1 <= contexts <= 16 or endian not in ('little', 'big'):
        raise ValueError('invalid state descriptor')
    size = (w + 7) // 8
    stride = 2 * size + 1
    if type(payload) is not bytes or len(payload) != contexts * stride:
        raise ValueError('state length must match exactly')
    out = tuple((int.from_bytes(payload[p:p+size], endian),
                 int.from_bytes(payload[p+size:p+2*size], endian), payload[p+2*size])
                for p in range(0, len(payload), stride))
    validate_state(out, w)  # reject unused high bits and non-bit carry
    return out


@dataclass(frozen=True)
class Event:
    identity: int
    context: int
    opcode: str
    destination: int
    source: int | None
    immediate: int

    def validate(self, contexts: int, w: int) -> None:
        _width(w)
        if type(self.identity) is not int or not 0 <= self.identity < 512:
            raise ValueError('invalid event identity')
        if type(self.context) is not int or not 0 <= self.context < contexts:
            raise ValueError('invalid context')
        if self.opcode not in OPS or type(self.destination) is not int or self.destination not in (0, 1):
            raise ValueError('invalid operation or destination')
        if self.source is not None and (type(self.source) is not int or self.source not in (0, 1)):
            raise ValueError('invalid source register')
        if type(self.immediate) is not int or not 0 <= self.immediate < 1 << w:
            raise ValueError('immediate outside virtual width')


def reference_step(state: State, event: Event, w: int) -> tuple[State, tuple[int, int, int]]:
    validate_state(state, w)
    event.validate(len(state), w)
    row = list(state[event.context])
    operand = event.immediate if event.source is None else row[event.source]
    value, carry = reference_alu(event.opcode, row[event.destination], operand, row[2], w)
    row[event.destination], row[2] = value, carry
    rows = list(state); rows[event.context] = tuple(row)
    return tuple(rows), (event.identity, value, carry)


def adapter_step(state: State, event: Event, cap: Capability) -> tuple[State, tuple[int, int, int]]:
    validate_state(state, cap.width)
    event.validate(len(state), cap.width)
    selected = state[event.context]
    rhs = selected[event.source] if event.source is not None else event.immediate
    result, flag = adapter_alu(event.opcode, selected[event.destination], rhs, selected[2], cap)
    first, second = selected[0], selected[1]
    if event.destination == 0:
        first = result
    else:
        second = result
    changed = (first, second, flag)
    new = state[:event.context] + (changed,) + state[event.context+1:]
    return new, (event.identity, result, flag)


def accesses(event: Event) -> tuple[set[int], set[int]]:
    base = 3 * event.context
    reads = set() if event.opcode == 'COPY' else {base + event.destination}
    if event.source is not None:
        reads.add(base + event.source)
    # COPY/XOR preserve and expose carry in the distinguishing result.
    if event.opcode != 'ADD':
        reads.add(base + 2)
    writes = {base + event.destination}
    if event.opcode in ('ADD', 'ADC'):
        writes.add(base + 2)
    return reads, writes


def dependence_order(events: tuple[Event, ...]) -> tuple[int, ...]:
    if len(events) > 512 or any(e.identity != i for i, e in enumerate(events)):
        raise ValueError('dependence construction requires ordered contiguous identities')
    rw = [accesses(e) for e in events]
    edges = []
    for j, (rj, wj) in enumerate(rw):
        for i, (ri, wi) in enumerate(rw[:j]):
            if (wi & (rj | wj)) or (ri & wj):
                edges.append((i, j))
    return closure(len(events), edges)
