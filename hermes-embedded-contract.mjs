// Exact, read/cancel-only contract shared by relay and private service.
export const PANEL_PREFIX='/api/jarvis/hermes-panel';
export const PANEL_COOKIE='JarvisHermesSession';
export function panelRoute(method,path,{admissionEnabled=false,voiceEnabled=false}={}){
 const sub=path.slice(PANEL_PREFIX.length);
 if(!(path===PANEL_PREFIX||path.startsWith(PANEL_PREFIX+'/')))return false;
 if(sub==='/session')return ['GET','POST','DELETE'].includes(method);
 if(sub==='/hybrid/ask')return voiceEnabled&&admissionEnabled&&method==='POST';
 if(sub==='/hermes/missions'&&method==='POST')return admissionEnabled;
 if(['/hermes/config','/hermes/availability','/hermes/missions'].includes(sub))return method==='GET';
 return method==='GET'&&/^\/hermes\/missions\/[A-Za-z0-9-]{1,128}(?:\/(?:results|events))?$/.test(sub)
  ||method==='POST'&&/^\/hermes\/missions\/[A-Za-z0-9-]{1,128}\/cancel$/.test(sub);
}
