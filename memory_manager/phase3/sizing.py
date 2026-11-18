"""Pure laboratory sizing policy. No Proxmox mutation or implicit approval."""
import math

MIB = 1024 ** 2
HOST_RESERVE_MIB = 1024
QEMU_ALLOWANCE_MIB = 256  # Planning allowance, to measure during the next pilot.


def plan(vm_mib=3072, balloon_growth_bytes=0):
    if type(vm_mib) is not int or vm_mib not in (2048, 3072):
        raise ValueError('Only the reviewed 2/3 GiB scenarios')
    if type(balloon_growth_bytes) is not int or balloon_growth_bytes < 0:
        raise ValueError('Measured balloon growth required')
    runtime = vm_mib - 1024
    return {'vm_mib': vm_mib, 'runtime_max_mib': runtime,
            'os_budget_mib': 512, 'guest_reserve_mib': 512,
            'qemu_allowance_mib': QEMU_ALLOWANCE_MIB,
            'host_reserve_mib': HOST_RESERVE_MIB,
            'balloon_growth_mib': math.ceil(balloon_growth_bytes / MIB),
            'host_required_bytes': (vm_mib + QEMU_ALLOWANCE_MIB + HOST_RESERVE_MIB) * MIB + balloon_growth_bytes,
            'runtime_limit_previously_exercised': vm_mib == 3072,
            'target_vm_size_tested': False}


def balloon_growth(state):
    """Reserve possible reinflation; do not rely on shrinking another VM."""
    growth = 0
    for vid in ('103', '201'):
        guest = state['guests'][vid]
        maximum, actual = guest['maximum_mib'], guest['actual_bytes']
        if type(maximum) is not int or type(actual) is not int or not 0 < actual <= maximum * MIB:
            raise ValueError('Unknown guest allocation')
        growth += maximum * MIB - actual
    return growth


def admission(samples, vm_mib=3072, *, now):
    """15 consecutive fresh host samples; fail closed, never starts anything."""
    if len(samples) < 15:
        return {'admitted': False, 'reason': 'insufficient_samples'}
    rows = samples[-15:]
    required = {'at', 'mem_available_bytes', 'balloon_growth_bytes', 'psi_full_avg10', 'pswpout'}
    try:
        if not math.isfinite(now): raise ValueError('Clock')
        for row in rows:
            if not required <= row.keys(): raise ValueError('Missing metric')
            if any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) or row[k] < 0 for k in required):
                raise ValueError('Invalid metric')
            if any(type(row[k]) is not int for k in ('mem_available_bytes', 'balloon_growth_bytes', 'pswpout')):
                raise ValueError('Integer metric required')
        if not 28 <= rows[-1]['at'] - rows[0]['at'] <= 45:
            raise ValueError('Observation duration')
        if not 0 <= now - rows[-1]['at'] <= 5 or now - rows[0]['at'] > 45:
            raise ValueError('Stale telemetry')
        if any(not 0 < b['at'] - a['at'] <= 3 for a, b in zip(rows, rows[1:])):
            raise ValueError('Sampling gap')
        if any(row['mem_available_bytes'] < plan(vm_mib, row['balloon_growth_bytes'])['host_required_bytes'] for row in rows):
            return {'admitted': False, 'reason': 'host_capacity'}
        if any(row['psi_full_avg10'] > 1 for row in rows) or any(b['pswpout'] != a['pswpout'] for a, b in zip(rows, rows[1:])):
            return {'admitted': False, 'reason': 'host_pressure_or_swap_activity'}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {'admitted': False, 'reason': 'invalid_or_stale_telemetry'}
    return {'admitted': True, 'reason': 'capacity_only_not_authorization'}
