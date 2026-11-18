"""Windows Job Object supervisor. Native API execution needs Windows validation.

A resource/lifecycle boundary, NOT a filesystem or network sandbox. Do not use
native gateway detach/start helpers: the process must stay in this owned job.
"""
import ctypes as c
import os
import subprocess
import time

U32, U64, SIZE, HANDLE = c.c_uint32, c.c_uint64, c.c_size_t, c.c_void_p


class Basic(c.Structure):
    _fields_ = [('ProcessTime', c.c_int64), ('JobTime', c.c_int64), ('Flags', U32),
                ('MinWS', SIZE), ('MaxWS', SIZE), ('Active', U32), ('Affinity', SIZE),
                ('Priority', U32), ('Scheduling', U32)]


class IO(c.Structure):
    _fields_ = [(name, U64) for name in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes', 'OtherBytes')]


class Extended(c.Structure):
    _fields_ = [('Basic', Basic), ('IO', IO), ('ProcessMemory', SIZE), ('JobMemory', SIZE),
                ('PeakProcessMemory', SIZE), ('PeakJobMemory', SIZE)]


class CPU(c.Structure):
    _fields_ = [('Flags', U32), ('Rate', U32)]


class Startup(c.Structure):
    _fields_ = [('cb', U32), ('reserved', c.c_wchar_p), ('desktop', c.c_wchar_p), ('title', c.c_wchar_p)] + [
        (name, U32) for name in ('x', 'y', 'sx', 'sy', 'cols', 'rows', 'fill', 'flags')] + [
        ('show', c.c_uint16), ('cbReserved', c.c_uint16), ('lpReserved', c.c_void_p),
        ('stdin', HANDLE), ('stdout', HANDLE), ('stderr', HANDLE)]


class Process(c.Structure):
    _fields_ = [('process', HANDLE), ('thread', HANDLE), ('pid', U32), ('tid', U32)]


def supervise(command, env, cwd, *, seconds=300, stop_requested=lambda: False, resource_profile="hermes"):
    if os.name != 'nt': raise RuntimeError('Windows-only supervisor; never emulate native proof')
    if resource_profile not in {'hermes', 'ollama'}: raise ValueError('Unknown owned resource profile')
    max_seconds, memory_limit, cpu_rate = ((300, 2 * 1024**3, 2000) if resource_profile == 'hermes'
                                           else (1800, 12 * 1024**3, 8000))
    if not 1 <= seconds <= max_seconds: raise ValueError('Bounded pilot duration required')
    api = c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([c.c_void_p, c.c_wchar_p], HANDLE),
        'SetInformationJobObject': ([HANDLE, c.c_int, c.c_void_p, U32], c.c_int),
        'QueryInformationJobObject': ([HANDLE, c.c_int, c.c_void_p, U32, c.c_void_p], c.c_int),
        'AssignProcessToJobObject': ([HANDLE, HANDLE], c.c_int),
        'ResumeThread': ([HANDLE], U32), 'CloseHandle': ([HANDLE], c.c_int),
        'GetExitCodeProcess': ([HANDLE, c.POINTER(U32)], c.c_int),
        'TerminateProcess': ([HANDLE, U32], c.c_int),
        'WaitForSingleObject': ([HANDLE, U32], U32),
        'CreateProcessW': ([c.c_wchar_p, c.c_wchar_p, c.c_void_p, c.c_void_p, c.c_int,
                            U32, c.c_void_p, c.c_wchar_p, c.POINTER(Startup), c.POINTER(Process)], c.c_int)}
    for name, (args, result) in signatures.items():
        getattr(api, name).argtypes = args; getattr(api, name).restype = result
    def checked(value):
        if not value: raise OSError(c.get_last_error(), 'Windows job API operation failed')
        return value
    job = checked(api.CreateJobObjectW(None, None))
    process = Process()
    report = {}
    try:
        limits = Extended()
        # No BREAKAWAY flags. Child processes inherit the job by default.
        limits.Basic.Flags = 0x2000 | 0x200 | 0x8  # KILL_ON_JOB_CLOSE, JOB_MEMORY, ACTIVE_PROCESS
        limits.Basic.Active = 32
        limits.JobMemory = memory_limit
        checked(api.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
        cpu = CPU(1 | 4, cpu_rate)  # ENABLE + HARD_CAP; host-selected resource profile
        checked(api.SetInformationJobObject(job, 15, c.byref(cpu), c.sizeof(cpu)))
        startup = Startup(); startup.cb = c.sizeof(startup)
        block = c.create_unicode_buffer('\0'.join(k + '=' + v for k, v in sorted(env.items(), key=lambda p: p[0].upper())) + '\0\0')
        line = c.create_unicode_buffer(subprocess.list2cmdline(command))
        # Suspended => no runtime instruction executes before successful assignment.
        checked(api.CreateProcessW(command[0], line, None, None, False,
                                  0x4 | 0x400 | 0x08000000, block, str(cwd), c.byref(startup), c.byref(process)))
        try:
            checked(api.AssignProcessToJobObject(job, process.process))
        except BaseException:
            api.TerminateProcess(process.process, 1)  # Only the suspended child we created.
            raise
        if api.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise OSError('Cannot resume the owned child')
        started = time.monotonic()
        reason = 'exited'
        while True:
            waited = api.WaitForSingleObject(process.process, 250)
            if waited == 0: break
            if waited != 0x102: raise OSError('Owned process wait failed')
            stopping = stop_requested()
            if stopping or time.monotonic() - started >= seconds:
                reason = 'operator_stop' if stopping else 'deadline'
                break
        checked(api.QueryInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits), None))
        code = U32(); checked(api.GetExitCodeProcess(process.process, c.byref(code)))
        report = {'pid': process.pid, 'reason': reason, 'exit_code_before_job_close': code.value,
                'resource_profile': resource_profile, 'memory_limit_bytes': limits.JobMemory,
                'limit_flags': limits.Basic.Flags, 'peak_job_memory_bytes': limits.PeakJobMemory, 'peak_process_memory_bytes': limits.PeakProcessMemory,
                'elapsed_seconds': time.monotonic() - started}
        return report
    finally:
        api.CloseHandle(job)  # Stops only this job and its descendants, never Ollama/Kryptex.
        if process.process:
            report['owned_process_stopped_after_close'] = api.WaitForSingleObject(process.process, 5000) == 0
        for handle in (process.thread, process.process):
            if handle: api.CloseHandle(handle)
