import {spawn} from 'node:child_process';
export function usage(action, data = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', ['/home/user/workspace/jarvis/usage.py', action], {stdio: ['pipe', 'pipe', 'ignore']});
    let output = '';
    child.stdout.on('data', chunk => output += chunk);
    child.on('error', () => reject(Error('Suivi des coûts indisponible.')));
    child.stdin.on('error', () => {});
    child.on('close', () => {
      try {
        const result = JSON.parse(output);
        result.ok ? resolve(result.data) : reject(Error(result.error));
      } catch { reject(Error('Suivi des coûts indisponible.')); }
    });
    child.stdin.end(JSON.stringify(data));
  });
}
