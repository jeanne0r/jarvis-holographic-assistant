// DOM-only rendering: never HTML, remote assets, model instructions or authority.
(()=>{
 const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 function inline(parent,text){
  const pattern=/(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\s]+\))/g;let offset=0;
  for(const match of text.matchAll(pattern)){
   parent.append(document.createTextNode(text.slice(offset,match.index)));const token=match[0];
   if(token[0]==='`'&&/^(synthetic|mission):\/\//.test(token.slice(1,-1))){
    const source=node('button','Source liée');source.type='button';source.className='hermes-source-link';
    source.onclick=()=>{const details=document.getElementById('hermesSourcesDetails');if(details){details.open=true;details.querySelector('summary')?.focus()}};parent.append(source);
   }else if(token[0]==='`')parent.append(node('code',token.slice(1,-1)));
   else if(token.startsWith('**'))parent.append(node('strong',token.slice(2,-2)));
   else {const split=token.indexOf(']('),label=token.slice(1,split),target=token.slice(split+2,-1);let url;
    try{url=new URL(target)}catch{}
    if(url&&['https:','http:'].includes(url.protocol)&&!url.username&&!url.password){const a=node('a',label);a.href=url.href;a.rel='noopener noreferrer';a.target='_blank';parent.append(a)}
    else parent.append(document.createTextNode(token));
   }
   offset=match.index+token.length;
  }
  parent.append(document.createTextNode(text.slice(offset)));
 }
 function markdown(text){
  const root=node('div');root.className='hermes-markdown';text=String(text);
  // Very large results remain available as literal text; never silently truncate.
  if(text.length>262144){root.append(node('pre',text));return root}
  const lines=text.replace(/\r\n?/g,'\n').split('\n');let list=null;
  for(let i=0;i<lines.length;i++){
   const line=lines[i];if(!line.trim()){list=null;continue}
   if(line.startsWith('```')){list=null;const code=[];while(++i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i]);const pre=node('pre');pre.append(node('code',code.join('\n')));root.append(pre);continue}
   if(i+1<lines.length&&line.includes('|')&&/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i+1])){
    list=null;const table=node('table'),head=node('thead'),body=node('tbody');
    const cells=row=>row.trim().replace(/^\||\|$/g,'').split('|');
    const tr=node('tr');for(const cell of cells(line)){const th=node('th');inline(th,cell.trim());tr.append(th)}head.append(tr);i++;
    while(i+1<lines.length&&lines[i+1].includes('|')&&lines[i+1].trim()){const row=node('tr');for(const cell of cells(lines[++i])){const td=node('td');inline(td,cell.trim());row.append(td)}body.append(row)}
    table.append(head,body);const scroll=node('div');scroll.className='hermes-table-scroll';scroll.append(table);root.append(scroll);continue;
   }
   const heading=/^(#{1,6})\s+(.*)$/.exec(line),bullet=/^\s*(?:[-*+] |\d+[.)] )(.*)$/.exec(line);
   if(bullet){const type=/^\s*\d/.test(line)?'OL':'UL';if(!list||list.tagName!==type){list=node(type.toLowerCase());root.append(list)}const li=node('li');inline(li,bullet[1]);list.append(li);continue}
   list=null;const block=node(heading?'h'+Math.min(heading[1].length+1,6):line.startsWith('> ')?'blockquote':'p');inline(block,heading?heading[2]:line.startsWith('> ')?line.slice(2):line);root.append(block);
  }
  return root;
 }
 const terminal=new Set(['completed','failed','cancelled']);
 const demo=m=>m.synthetic===true||/synthétique|démonstration/iu.test(m.objective||m.definition?.objective||'');
 function title(m){const value=m.objective||m.definition?.objective||'Mission';return demo(m)&&/doselab/iu.test(value)?'DoseLab · configuration des cellules':value.length>96?value.slice(0,93)+'…':value}
 function date(value){if(value==null||value==='')return null;const d=new Date(typeof value==='number'?(value<1e12?value*1000:value):value);return Number.isFinite(d.getTime())?d:null}
 function timing(m){const created=date(m.created),updated=date(m.updated);let text=created?created.toLocaleString('fr-CH',{dateStyle:'medium',timeStyle:'short'}):'Date non fournie';if(terminal.has(m.state)&&created&&updated&&updated>=created){const seconds=Math.round((updated-created)/1000);text+=' · Durée totale : '+(seconds<60?seconds+' s':Math.floor(seconds/60)+' min '+seconds%60+' s')}return text}
 function visible(items,{history=false,hideDemos=false}={}){return items.filter(m=>(!hideDemos||!demo(m))&&(history||!['failed','cancelled'].includes(m.state))).sort((a,b)=>Number(terminal.has(a.state))-Number(terminal.has(b.state))||((date(b.created)?.getTime()||0)-(date(a.created)?.getTime()||0))).filter((m,i,array)=>history||!terminal.has(m.state)||array.slice(0,i).filter(v=>terminal.has(v.state)).length<5)}
 function availability(worker){if(worker.reason||worker.state==='unavailable')return 'Exécution en pause · historique disponible.';if(!worker.fresh)return 'Exécuteur non disponible ou présence non confirmée · missions conservées.';return ({ready:'Prêt à travailler.',gpu_busy:'Carte graphique occupée · missions en attente.',uncertain:'État à vérifier · aucune relance automatique.',offline:'Exécuteur indisponible · missions conservées.'})[worker.state]||'Disponibilité à vérifier · historique conservé.'}
 function failure(error){return ({401:'Connecte-toi pour consulter tes missions.',403:'Ton compte ne permet pas cet accès.',404:'Les missions ne sont pas activées.',409:'Vérifie l’historique avant toute nouvelle demande.',503:'Les missions sont momentanément indisponibles. Jarvis reste utilisable.'})[error.status]||'Impossible d’actualiser les missions. Aucun nouvel envoi automatique.'}
 globalThis.JarvisMissionView=Object.freeze({markdown,demo,title,timing,visible,availability,failure});
})();
