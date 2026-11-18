import os,sys,json,pathlib,subprocess,ctypes,time,uuid
if os.name != "nt" or sys.argv[1:] != ["--approved"]: raise SystemExit("Approved Windows-only operator probe")
sys.path.insert(0,r'C:\JarvisHermesLab\app')
from memory_manager.phase4.job import supervise
root=pathlib.Path(r'C:\JarvisHermesLab\runs');root=root / ('job-probe-'+uuid.uuid4().hex);root.mkdir(exist_ok=False)
python=r'C:\JarvisHermesLab\runtime\Scripts\python.exe'
results={}
def run(name,code,seconds):
 r=supervise([python,'-I','-S','-c',code],dict(os.environ),root,seconds=seconds)
 results[name]=r
 assert r['owned_process_stopped_after_close']
 assert r['memory_limit_bytes']==2*1024**3 and r['limit_flags'] & 0x200
run('exit',"import pathlib;pathlib.Path('normal.txt').write_text('ok')",10)
assert results['exit']['exit_code_before_job_close']==0
child="import time,pathlib,os; b=bytearray(64*1024**2);pathlib.Path('descendant.pid').write_text(str(os.getpid()));time.sleep(60)"
code="import subprocess,time;subprocess.Popen("+repr([python,'-I','-S','-c',child])+");time.sleep(60)"
run('deadline_descendant',code,4)
pid=int((root/'descendant.pid').read_text())
k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p;k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];k.WaitForSingleObject.restype=ctypes.c_uint32;k.CloseHandle.argtypes=[ctypes.c_void_p]
h=k.OpenProcess(0x100000,False,pid)
results['descendant_stopped']=not h or k.WaitForSingleObject(h,5000)==0
if h:k.CloseHandle(h)
assert results['descendant_stopped']
code="import pathlib\ntry:\n b=bytearray(3*1024**3)\n pathlib.Path('allocation.txt').write_text('unexpected')\nexcept MemoryError:\n pathlib.Path('allocation.txt').write_text('denied')"
run('memory_ceiling',code,20)
results['allocation']=(root/'allocation.txt').read_text();assert results['allocation']=='denied'
results['peak_counter_note']='PeakJobMemory includes an attempted rejected 3GiB allocation; this is not RSS.'
results['passed']=True
(root/'result.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
