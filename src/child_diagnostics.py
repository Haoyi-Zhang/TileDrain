"""Failure-only diagnostics; never infer the cause of a termination signal."""
from __future__ import annotations

import json
import signal


def failure_record(arguments: list[str], returncode: int | None,
                   stdout: str | bytes | None, stderr: str | bytes | None) -> dict:
    """None denotes a controller wall timeout; a completed child must be nonzero."""
    if returncode == 0:
        raise ValueError('a successful child is not a failure record')

    def text(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return value or ''

    number = -returncode if returncode is not None and returncode < 0 else None
    name = None
    if number is not None:
        try:
            name = signal.Signals(number).name
        except ValueError:
            pass
    return {
        'status': 'failed',
        'command': list(arguments),
        'returncode': returncode,
        'controller_wall_timeout': returncode is None,
        'termination_signal_number': number,
        'termination_signal_name': name,
        'stdout': text(stdout),
        'stderr': text(stderr),
        'scope': 'Termination diagnostics only; a signal does not establish its cause.',
    }


def failure_message(record: dict) -> str:
    return 'child failed:\n' + json.dumps(record, indent=2, ensure_ascii=True)
