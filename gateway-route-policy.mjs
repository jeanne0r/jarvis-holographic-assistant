// Explicit Node 18 route registry. No provider, shell, database or physical imports.
const rows=[];
function add(path,methods,permission,options={}){
 for(const method of methods.split(' '))rows.push(Object.freeze({path,method,permission,identity:'human',effect:'read',clients:[],...options}));
}
add('/api/health','GET','public',{identity:'public',effect:'minimal-health-only',clients:['monitor']});
add('/api/jarvis/session','GET POST DELETE','session',{identity:'session-protocol',effect:'human-session',clients:['auth-client']});
const jarvis={
 'ask':['POST','conversation','model/tools/archive'],
 'capabilities':['GET','capabilities.read','configuration'], 'capabilities/run':['POST','capabilities.execute','external-or-physical'],
 'evolution/status':['GET','development.read','development-results'],'evolution/diff':['GET','development.read','file-read'],
 'conversations/record':['POST','memory.write','archive-write'],
 'memory/map':['GET','memory.read','memory-with-common'], 'memory/status':['GET','memory.read','memory-with-common'],
 'voice/status':['GET','voice','configuration'],'live/status':['GET','voice','configuration'],
 'openai/usage':['GET','usage.read','provider-request'],'live/costs':['GET','usage.read','usage-read'],
 'live/usage':['POST','usage.write','usage-write'],'live/balance':['POST','usage.manage','usage-write'],
 'live/tool':['POST','native.tools','model-selected-tools'],'live/session':['POST','native.session','provider-session'],
 'voice/session':['POST','voice','voice-session'], 'voice/transcribe':['POST','voice','paid-provider'], 'voice/speak':['POST','voice','paid-provider-stream'],
 'move':['POST','memory.move','cross-space-write'],'docs':['GET','memory.read','memory-read'],'doc':['GET','memory.read','memory-read'],
 'sync':['POST','memory.sync','global-import'],'notes':['POST','memory.write','memory-write'],'import':['POST','memory.import','file-import'],
 'hermes/availability':['GET','missions.read','worker-heartbeat'],'hermes/config':['GET','missions.read','feature-state'],'hermes/missions':['GET','missions.read','mission-read'],
};
for(const [p,[methods,permission,effect]] of Object.entries(jarvis))add('/api/jarvis/'+p,methods,permission,{space:true,effect,clients:['jarvis-web','iphone-web'],resource:['ask','docs','doc','capabilities/run','live/tool','live/session','move','sync','import','memory/map','memory/status','evolution/status','evolution/diff'].includes(p)});
add('/api/jarvis/hermes/missions','POST','missions.create',{space:true,effect:'synthetic-admission',clients:['missions-panel','hybrid-facade']});
for(const suffix of ['', '/events','/results'])add('/api/jarvis/hermes/missions/:id'+suffix,'GET','missions.read',{space:true,resource:true,effect:'mission-read',clients:['missions-panel']});
add('/api/jarvis/hermes/missions/:id/cancel','POST','missions.cancel',{space:true,resource:true,effect:'cancel-request',clients:['missions-panel']});
add('/api/jarvis/hermes/missions/:id/approvals','POST','missions.approve',{space:true,resource:true,effect:'human-approval',clients:['missions-panel'],approval:true});
add('/api/projects','GET','projects.read',{resource:true,clients:['gateway-ui'],effect:'filesystem-list'});
add('/api/tree','GET','files.read',{resource:true,clients:['gateway-ui'],effect:'filesystem-read-and-mkdir'});
add('/api/chat','GET','chat.read',{resource:true,clients:['gateway-ui'],effect:'conversation-read'});
add('/api/chat','DELETE','chat.delete',{resource:true,clients:['gateway-ui'],effect:'conversation-delete'});
add('/api/runs','GET','runs.read',{resource:true,clients:['gateway-ui'],effect:'run-list'});
add('/api/runs','POST','runs.create',{resource:true,clients:['gateway-ui'],effect:'shell/network/files'});
for(const suffix of ['','/events'])add('/api/runs/:id'+suffix,'GET','runs.read',{resource:true,clients:['gateway-ui'],effect:'run-output'});
add('/api/s9/control','GET','physical.status',{clients:['s9-ui'],effect:'equipment-status'});
add('/api/s9/power','POST','physical.s9.power',{physical:true,resource:true,effect:'physical-power',clients:['s9-ui']});
add('/api/dosing-calibration/run','POST','physical.dosing.calibrate',{physical:true,resource:true,effect:'physical-calibration',clients:['calibration-ui']});
add('/api/dosing-calibration/latest','GET','calibration.read',{clients:['calibration-ui'],effect:'measurement-read'});
for(const name of ['magic-mirror','mining-report','home-report','energy-live','nilm-report'])add('/api/'+name,'GET','reports.read',{clients:['mirror-ui','dashboard'],effect:'private-telemetry'});
add('/api/mirror/apple','GET','calendar.read',{clients:['mirror-ui'],effect:'personal-data'});
add('/api/mirror/apple','POST','calendar.configure',{resource:true,clients:['mirror-ui'],effect:'account-configuration'});
add('/api/mirror/tasks','GET','tasks.read',{clients:['mirror-ui'],effect:'task-read'});
add('/api/mirror/tasks','POST PATCH DELETE','tasks.write',{resource:true,clients:['mirror-ui'],effect:'task-write'});
for(const name of ['status','calendars','events','addressbooks','contacts'])add('/api/icloud/'+name,'GET','calendar.read',{clients:['mirror-ui'],effect:'personal-data'});
add('/api/fridge/stock','GET','fridge.read',{clients:['fridge-ui'],effect:'inventory-read'});
add('/api/fridge/product/:id','GET','fridge.read',{clients:['fridge-ui'],effect:'product-read/network'});
for(const name of ['vision','barcode','date','name','items','remove-by-barcode'])add('/api/fridge/'+name,'POST',name==='vision'?'fridge.analyse':'fridge.write',{clients:['fridge-ui'],effect:name==='vision'?'paid-vision':'inventory/network'});
add('/api/fridge/items/:id','PATCH PUT','fridge.write',{clients:['fridge-ui'],resource:true,effect:'inventory-write'});
add('/api/fridge/items/:id/remove','POST','fridge.write',{clients:['fridge-ui'],resource:true,effect:'inventory-write'});
for(const name of ['status','image'])add('/api/astro/'+name,'GET','astro.read',{clients:['astro-ui'],effect:'private-display'});
add('/api/astro/connect','POST','astro.connect',{clients:['astro-ui'],resource:true,effect:'upstream-network/config'});
for(const name of ['start','answer','close'])add('/api/german/'+name,'POST','german.use',{clients:['german-ui'],resource:name!=='start',effect:name==='close'?'session-delete':'paid-model/session'});
for(const name of ['report','fast','lightning','trail-lab','loss-audit','annual-trades.csv','dex-trades.csv','analysis.csv'])add('/api/solana-paper/'+name,'GET HEAD','paper.read',{clients:['solana-ui'],effect:'simulation-data-read'});
add('/api/solana-paper/runs/:epoch/:file','GET HEAD','paper.read',{resource:true,clients:['solana-ui'],effect:'archive-read'});
// Account/data routes also require a server-bound business adapter.
for(let i=0;i<rows.length;i++)if(!rows[i].path.startsWith('/api/jarvis/')&&rows[i].path!=='/api/health')rows[i]=Object.freeze({...rows[i],resource:true});
export const routeMatrix=Object.freeze(rows);
const compiled=rows.map(row=>({...row,re:new RegExp('^'+row.path.split('/').map(s=>s.startsWith(':')?'[^/]+':s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('/')+'$')}));
export function classify(method,path){return compiled.find(r=>r.method===method&&r.re.test(path))||null}
export const requestIdentity=new WeakMap();
export function authorize({method,path,identity,space,origin,expectedOrigin,resourceAllowed=false,physicalApproval=false}){
 const row=classify(method,path);
 if(!row)return {allowed:false,status:403,reason:'unclassified-route'};
 if(row.identity==='public')return {allowed:true,row};
 if(row.identity==='session-protocol')return {allowed:true,row}; // sessionRegistry enforces its own origin/credentials.
 if(!identity)return {allowed:false,status:401,reason:'authentication'};
 if(identity.kind!=='human')return {allowed:false,status:403,reason:'human-required'};
 if(!identity.roles?.includes(row.permission))return {allowed:false,status:403,reason:'permission'};
 if(row.space&&(!space||!identity.spaces?.includes(space)))return {allowed:false,status:403,reason:'space'};
 if(!['GET','HEAD'].includes(method)&&origin!==expectedOrigin)return {allowed:false,status:403,reason:'origin'};
 if(row.resource&&!resourceAllowed)return {allowed:false,status:403,reason:'resource-adapter-required'};
 if(row.physical&&!physicalApproval)return {allowed:false,status:403,reason:'physical-approval-required'};
 return {allowed:true,row};
}
