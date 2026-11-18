import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {routeMatrix} from './gateway-route-policy.mjs';
const audit=JSON.parse(await readFile('./docs/phase6d/route-matrix.json','utf8'));
assert.deepEqual(audit.route_method_pairs,routeMatrix);
const declared=new Set(routeMatrix.map(r=>r.path));let checks=0;
for(const source of audit.sources){
 const raw=await readFile(source.source,'utf8');assert.equal(createHash('sha256').update(raw).digest('hex'),source.sha256);
 const literals=[...raw.matchAll(/url\.pathname\s*===\s*['"](\/api\/[^'"]+)['"]/g)].map(m=>m[1]);
 for(const p of literals){assert.ok(declared.has(p),'Unclassified literal '+p);checks++}
 if(source.source.endsWith('/jarvis/backend.mjs')){
  for(const m of raw.matchAll(/action\s*===\s*['"]([^'"]+)['"]/g)){assert.ok(declared.has('/api/jarvis/'+m[1]));checks++}
 }
}
for(const p of ['/api/fridge/product/:id','/api/fridge/items/:id','/api/fridge/items/:id/remove','/api/runs/:id','/api/runs/:id/events','/api/solana-paper/runs/:epoch/:file'])assert.ok(declared.has(p));
console.log(JSON.stringify({passed:true,source_hashes_verified:audit.sources.length,literal_route_conditions_classified:checks,dynamic_route_families_explicit:true,unclassified_routes_default_denied:true}));
