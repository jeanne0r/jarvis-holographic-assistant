export const apps={astro:{label:'Astro',path:'/astro/index.html'},allemand:{label:'Allemand',path:'/allemand/index.html'},verbes:{label:'Verbes en poche',path:'/verbes/index.html'}};
export function validateAction(a){
 if(!a||typeof a!=='object')return null;
 const str=v=>typeof v==='string'?v:'';
 switch(a.type){
 case 'capability':{try{const effect=JSON.parse(str(a.text));return effect&&['media','travel','evolution','web','interface'].includes(effect.type)?{type:'capability',effect}:null;}catch{return null;}}
 case 'switch_space':return ['user','amelie','malik','theo','commun'].includes(a.target)?{type:a.type,target:a.target}:null;
 case 'navigate':return ['galaxy','library','atelier','chat'].includes(a.target)?{type:a.type,target:a.target}:null;
 case 'open_app':return apps[a.target]?{type:a.type,target:a.target,...apps[a.target]}:null;
 case 'search':return str(a.text).trim()?{type:a.type,text:a.text.slice(0,500)}:null;
 case 'save_note':return str(a.title).trim()&&str(a.text).trim()?{type:a.type,title:a.title.slice(0,180),body:a.text.slice(0,30000),status:'Idée'}:null;
 default:return null;
 }
}
