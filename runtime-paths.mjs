import {fileURLToPath} from 'node:url';
import path from 'node:path';
export const PROJECT_ROOT=fileURLToPath(new URL('.',import.meta.url)).replace(/\/$/,'');
export const PUBLIC_ROOT=path.join(PROJECT_ROOT,'public');
export const WORKSPACE_ROOT=process.env.JARVIS_WORKSPACE_ROOT||PROJECT_ROOT;
export const CODEX_BIN=process.env.CODEX_BIN||'codex';
export const ENV_FILE=path.join(PROJECT_ROOT,'.env');
