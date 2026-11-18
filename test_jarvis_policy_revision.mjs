import assert from 'node:assert/strict';
import {createHash,randomBytes} from 'node:crypto';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {humanMissionsGateway} from './hermes-human-gateway.mjs';
const token=randomBytes(32).toString('base64url'),origin='https://192.0.2.16:8788';
const policy={revision:1,credentials:[{subject:'synthetic-alice',kind:'human',sha256:createHash('sha256').update(token).digest('hex'),expiresAt:Date.now()+60000}],grants:new Map([['synthetic-alice',['user']]]),roles:new Map([['synthetic-alice',['missions.read','missions.cancel']]])};
const sessions=sessionRegistry({...policy,origin});let assertions=0;
const eq=(a,b)=>{assert.deepEqual(a,b);assertions++};
const identity=sessions.authenticate({headers:{authorization:'Bearer '+token}});
eq(sessions.isActive(identity,'missions.read','user'),true);
const revoked={...policy,revision:2,roles:new Map([['synthetic-alice',[]]])};sessions.updatePolicy(revoked);
eq(sessions.isActive(identity,'missions.read','user'),false);
for(const rollback of [policy,{...policy,revision:2},{...policy,revision:undefined},{...policy,revision:0}]){assert.throws(()=>sessions.updatePolicy(rollback));assertions++}
eq(sessions.isActive(identity,'missions.read','user'),false);eq(sessions.policyRevision(),2);
sessions.updatePolicy({...revoked,revision:3,credentials:[]});eq(sessions.authenticate({headers:{authorization:'Bearer '+token}}),null);
const legacy=sessionRegistry({...policy,revision:undefined,origin});
assert.throws(()=>humanMissionsGateway({sessions:legacy,origin,refresh:async()=>{},sign:()=>'',audit:async()=>{}}));assertions++;
console.log(JSON.stringify({passed:true,assertions,stale_policy_cannot_restore_revoked_permissions:true,legacy_registry_not_promoted:true,production_modified:false}));
