import {spawn} from 'node:child_process';
const child=spawn('python3',['semantic/index.py'],{stdio:'inherit',env:process.env});child.on('exit',code=>{process.exitCode=code??1});
