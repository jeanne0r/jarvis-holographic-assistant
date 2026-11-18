"""Explicit namespace plan. Never executes Codex during preparation/tests."""
import os
from pathlib import Path

def plan(workspace,runtime,*,gateway_uid,executor_uid,model='gpt-6.1-sol',proxy_socket=None,tools_socket=None):
 if executor_uid==gateway_uid or executor_uid==0:raise PermissionError('Distinct non-root executor UID required')
 workspace=Path(workspace).resolve(strict=True);runtime=Path(runtime).resolve(strict=True)
 if not workspace.is_dir() or not runtime.is_dir() or workspace==runtime:raise ValueError('Independent roots')
 # Runtime is a reviewed read-only bundle containing the existing CLI, no home,
 # gateway, HA or Hermes configuration. No free --add-dir/network/sandbox flags.
 prefix=['/usr/bin/bwrap','--die-with-parent','--new-session','--unshare-all','--cap-drop','ALL','--clearenv',
 '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--tmpfs','/home','--dir','/home/agent',
 '--dir','/ipc','--dir','/workspace','--bind',str(workspace),'/workspace','--dir','/runtime','--ro-bind',str(runtime),'/runtime',
 '--setenv','HOME','/home/agent','--setenv','CODEX_HOME','/home/agent/.codex','--setenv','PATH','/usr/bin:/bin','--setenv','LANG','C.UTF-8','--chdir','/workspace']
 args=['/runtime/bin/codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','workspace-write',
 '-c','approval_policy="never"','-c','sandbox_workspace_write.network_access=false','--model',model,'--json','--output-last-message','/workspace/result.json','-']
 for feature in ['apps','plugins','multi_agent','multi_agent_v2','browser_use','computer_use','image_generation','hooks','memories']:args[-1:-1]=['--disable',feature]
 if proxy_socket is not None:
  source=Path(__file__).with_name('relay.py').resolve(strict=True)
  prefix+=['--ro-bind',str(Path(proxy_socket).resolve(strict=True)),'/ipc/provider.sock','--ro-bind',str(source),'/runtime/relay.py']
  args=['/usr/bin/python3','-I','/runtime/relay.py']+args[2:]
 if tools_socket is not None:
  source=Path(__file__).resolve().parents[3]/'codex-tool-proxy.mjs'
  if not source.is_file():raise ValueError('Reviewed tool proxy missing')
  prefix+=['--ro-bind',str(Path(tools_socket).resolve(strict=True)),'/ipc/tools.sock','--ro-bind',str(source),'/runtime/tool-proxy.mjs']
  args[-1:-1]=['-c','mcp_servers.jarvis.command="/usr/bin/node"','-c','mcp_servers.jarvis.args=["/runtime/tool-proxy.mjs"]','-c','mcp_servers.jarvis.required=true']
 return prefix+['--']+args

def check_uid(expected,gateway_uid):
 if os.getuid()!=expected or expected in (0,gateway_uid):raise PermissionError('Executor UID mismatch')
