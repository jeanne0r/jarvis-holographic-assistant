"""Operator-only temporary Ollama: fixed installed binary/store, loopback, owned Job TTL."""
import sys,os,json,subprocess,argparse,re,ctypes
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--approved',action='store_true',required=True);parser.add_argument('--trial-id',required=True);parser.add_argument('--owned-child',action='store_true');parser.add_argument('--seconds',type=int,default=1800);args=parser.parse_args()
if not 1 <= args.seconds <= 1800:raise SystemExit('Bounded operator window required')
if os.name != 'nt' or not re.fullmatch('[0-9a-f]{32}',args.trial_id):raise SystemExit('Approved Windows-only fresh pilot')
root=Path(r'C:\JarvisHermesLab');sys.path.insert(0,str(root/'app'))
from memory_manager.phase4.job import supervise
home=root/'runs'/args.trial_id
if args.owned_child:
    if not home.is_dir():raise SystemExit('Fresh operator home required')
    with open(home/'ollama-private.log','ab',buffering=0) as log:
        raise SystemExit(subprocess.call([r'C:\Users\winuser\AppData\Local\Programs\Ollama\ollama.exe','serve'],stdout=log,stderr=log))
home.mkdir(exist_ok=False)
# Repeat the existing deterministic hardware/miner guard before creating a workload.
ps=r'''$ErrorActionPreference='Stop';
$l=@(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue);
$p=@(Get-Process | Where-Object {$_.Name -match '(?i)(miner|^kryptex_.+|t-rex|gminer|xmrig)'});
$g=@(& C:\Windows\System32\nvidia-smi.exe --query-gpu=memory.free,utilization.gpu --format=csv,noheader,nounits);
[pscustomobject]@{listeners=$l.Count;miners=$p.Count;gpu=$g;available_kib=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory}|ConvertTo-Json -Compress'''
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',ps],capture_output=True,timeout=10,check=True)
f=json.loads(r.stdout);free,util=map(float,f['gpu'][0].split(','))
# 18.11 (User): mining in parallel (miners/utilization no longer defer); VRAM, RAM and no listener decide.
if f['listeners'] or free<8500 or f['available_kib']*1024<16*1024**3:raise SystemExit('GPU memory short or existing listener; deferred')
binary=Path(r'C:\Users\winuser\AppData\Local\Programs\Ollama\ollama.exe')
models=Path(r'C:\Users\winuser\.ollama\models')
if not binary.is_file() or not models.is_dir():raise SystemExit('Existing installation missing')
env={k:os.environ[k] for k in ('SystemRoot','WINDIR','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMDATA','ProgramFiles','ProgramFiles(x86)','CommonProgramFiles','COMSPEC','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','TEMP','TMP','PATH') if k in os.environ}
env.update(OLLAMA_HOST='127.0.0.1:11434',OLLAMA_MODELS=str(models),OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1')
class MemoryStatus(ctypes.Structure):
    _fields_=[('length',ctypes.c_uint32),('load',ctypes.c_uint32)]+[(x,ctypes.c_uint64) for x in ('total','available','page','available_page','virtual','available_virtual','extended')]
def stopping():
    status=MemoryStatus();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):return True
    return (home/'stop.requested').exists() or status.available < 4*1024**3
report=supervise([sys.executable,'-I',str(Path(__file__).resolve()),'--approved','--trial-id',args.trial_id,'--owned-child'],env,root,seconds=args.seconds,resource_profile='ollama',stop_requested=stopping)
(home/'supervisor-result.json').write_text(json.dumps(report),encoding='utf-8')
print(json.dumps(report))
