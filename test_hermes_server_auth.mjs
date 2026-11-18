import assert from 'node:assert/strict';
import {createHash,randomBytes} from 'node:crypto';
import {serverAuthenticator} from './hermes-server-auth.mjs';
import {experimentalHermes} from './jarvis-hermes-experimental.mjs';
const token=randomBytes(32).toString('base64url');
let now=1000;
const authenticate=serverAuthenticator({credentials:[{sha256:createHash('sha256').update(token).digest('hex'),subject:'alice',expiresAt:2000}],grants:new Map([['alice',['private-a']]]),now:()=>now});
const req={headers:{authorization:'Bearer '+token,'x-profile':'admin','x-space':'private-b'}};
assert.deepEqual(authenticate(req),{subject:'alice',spaces:['private-a']});
assert.equal(authenticate({headers:{authorization:'Bearer '+randomBytes(32).toString('base64url'),'x-profile':'alice'}}),null);
assert.equal(authenticate({headers:{'x-profile':'alice'}}),null);
let calls=0;const client={scope:'private',async request(){calls++;return {status:200,body:{state:'queued'}}}};
const handler=experimentalHermes({enabled:true,authenticate,clients:new Map([['alice',new Map([['private-a',client]])]])});
async function request(space){const res={writeHead(s){this.status=s},end(b){this.body=b}};await handler({...req,method:'GET'},res,new URL('http://localhost/api/jarvis/hermes/missions/test?space='+space));return res.status}
assert.equal(await request('private-b'),403);assert.equal(calls,0);
assert.equal(await request('private-a'),200);assert.equal(calls,1);
now=2000;assert.equal(await request('private-a'),401);assert.equal(calls,1);
console.log('PASS server sessions: opaque token hash, expiry, independent ACL, forged visual profile denied; no production gateway');
