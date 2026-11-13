(() => {
 const $=s=>document.querySelector(s),section=$('#memory3dView'),canvas=$('#memory3dCanvas'),ctx=canvas.getContext('2d');
 const colors={'Intelligence artificielle':'#53e6f7','Maison & énergie':'#6ba8ff','Création & projets':'#c5a6ff','Exploration':'#f4bd83','Apprentissage':'#f48ebe','Idées libres':'#a5c3d4','Souvenirs':'#75c4eb'};
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let points=[],selected=null,projected=[],yaw=.45,pitch=-.18,zoom=1,auto=!reduced.matches,frame=0,last=0,w=1,h=1,request=0,abort=null,loadedSpace='',loading=false,space='',needle='',sourceSequence=0;
 const pointers=new Map();let drag=null,pinch=0;
 function active(){return !section.hidden&&!document.hidden;}
 function motion(){ $('#map3dMotion').textContent=auto?'Pause':'Animer';$('#map3dMotion').setAttribute('aria-pressed',String(auto)); }
 function schedule(){if(active()&&!frame)frame=requestAnimationFrame(draw);}
 function resize(){const r=canvas.getBoundingClientRect();w=r.width;h=r.height;const d=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.max(1,Math.round(w*d));canvas.height=Math.max(1,Math.round(h*d));ctx.setTransform(d,0,0,d,0,0);schedule();}
 function xyz(pos){const [x,y,z]=pos,c=Math.cos(yaw),s=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),xx=x*c+z*s,zz=z*c-x*s,yy=y*cp-zz*sp,depth=y*sp+zz*cp;const perspective=3.5/(3.5-depth);const scale=Math.min(w,h)*.32*zoom*perspective;return {x:w*.5+xx*scale,y:h*.5+yy*scale,z:depth,k:perspective};}
 function line(a,b,stroke){const aa=xyz(a),bb=xyz(b);ctx.strokeStyle=stroke;ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(aa.x,aa.y);ctx.lineTo(bb.x,bb.y);ctx.stroke();}
 function matches(p){return !needle||(p.title+' '+p.excerpt+' '+p.topic).toLocaleLowerCase('fr').includes(needle);}
 function draw(now){frame=0;if(!active())return;
  if(auto&&now-last<40){schedule();return;}
  if(auto&&now-last>35){yaw+=Math.min(80,now-last)*.00014;last=now;}
  ctx.clearRect(0,0,w,h);const glow=ctx.createRadialGradient(w*.5,h*.48,0,w*.5,h*.48,Math.min(w,h)*.7);glow.addColorStop(0,'#082f4555');glow.addColorStop(1,'#02080d00');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
  for(let v=-1;v<=1.01;v+=.25){line([-1,1,v],[1,1,v],'#22516b55');line([v,1,-1],[v,1,1],'#22516b55');}
  projected=points.map(p=>({...xyz(p.position),p})).sort((a,b)=>a.z-b.z);
  for(const item of projected){const {p,x,y,z,k}=item,match=matches(p),chosen=selected?.id===p.id;const r=(chosen?5:2.5)*k;ctx.globalAlpha=match?Math.max(.25,(z+2)/3):.065;ctx.fillStyle=colors[p.topic]||colors.Souvenirs;
   if(chosen){ctx.globalAlpha=1;ctx.shadowColor=ctx.fillStyle;ctx.shadowBlur=18;}
   ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
   if(chosen){ctx.strokeStyle='#d6fbff';ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,r+6,0,Math.PI*2);ctx.stroke();ctx.font='11px system-ui';ctx.fillStyle='#c5f5ff';const label=p.title.length>35?p.title.slice(0,34)+'…':p.title;ctx.fillText(label,Math.max(8,Math.min(w-220,x+14)),Math.max(15,y-13));}
  }
  ctx.globalAlpha=1;if(auto)schedule();
 }
 function choose(id){selected=points.find(p=>p.id===id)||null;$('#map3dPoint').value=selected?.id||'';
  $('#map3dTitle').textContent=selected?.title||'Chaque point vient de Qdrant.';
  $('#map3dMeta').textContent=selected?`${selected.topic} · ${selected.space==='shared'?'Shared':$('#spaceSelect').selectedOptions[0].textContent} · ${selected.source}`:'';
  $('#map3dExcerpt').textContent=selected?.excerpt||'Tourne la carte puis touche un point pour lire son extrait.';
  $('#map3dSource').hidden=!selected?.docId.startsWith('brain:');schedule();
 }
 function options(){const select=$('#map3dPoint');select.replaceChildren(new Option('Sélectionner un extrait…',''));for(const p of points.filter(matches))select.append(new Option(p.title,p.id));}
 async function load(force=false){const owner=$('#spaceSelect').value;if(!force&&loadedSpace===owner&&points.length){schedule();return;}if(loading&&space===owner&&!force)return;
  request++;const serial=request;abort?.abort();abort=new AbortController();space=owner;loadedSpace='';loading=true;points=[];choose('');options();$('#map3dLegend').replaceChildren();$('#map3dStatus').textContent='Lecture des vecteurs Qdrant et projection locale…';$('#map3dRefresh').disabled=true;schedule();
  try{const response=await fetch('/api/jarvis/memory/map?space='+encodeURIComponent(owner),{signal:abort.signal});const data=await response.json();if(!response.ok)throw Error(data.error||'Carte indisponible.');if(serial!==request||owner!==$('#spaceSelect').value)return;
   points=data.points;loadedSpace=owner;options();$('#map3dStatus').textContent=`${data.sampled} extraits projetés · ${data.documents} sources · ${Number(data.indexedPoints).toLocaleString('fr-CH')} extraits dans l’index de ces espaces`;
   const counts={};for(const p of points)counts[p.topic]=(counts[p.topic]||0)+1;
   for(const [topic,count] of Object.entries(counts)){const row=document.createElement('div'),dot=document.createElement('i'),text=document.createElement('span');dot.style.background=colors[topic]||colors.Souvenirs;text.textContent=topic+' · '+count;row.append(dot,text);$('#map3dLegend').append(row);}
   if(!points.length)$('#map3dStatus').textContent='Aucun extrait indexé et à jour pour cet espace. Actualise après l’indexation.';schedule();
  }catch(e){if(e.name!=='AbortError'&&serial===request)$('#map3dStatus').textContent=e.message||'La carte Qdrant est indisponible.';}
  finally{if(serial===request){loading=false;$('#map3dRefresh').disabled=false;}}
 }
 $('#map3dPoint').addEventListener('change',e=>{auto=false;motion();choose(e.target.value);});
 $('#map3dSearch').addEventListener('input',e=>{needle=e.target.value.trim().toLocaleLowerCase('fr');options();schedule();});
 $('#map3dBack').onclick=()=>document.querySelector('.nav[data-view="chat"]').click();
 $('#map3dMotion').onclick=()=>{auto=!auto;last=performance.now();motion();schedule();};
 $('#map3dRefresh').onclick=()=>load(true);
 $('#map3dReset').onclick=()=>{yaw=.45;pitch=-.18;zoom=1;schedule();};
 const setZoom=next=>{zoom=Math.max(.5,Math.min(3,next));schedule();};
 $('#map3dZoomIn').onclick=()=>setZoom(zoom*1.2);$('#map3dZoomOut').onclick=()=>setZoom(zoom/1.2);
 canvas.addEventListener('wheel',e=>{e.preventDefault();setZoom(zoom*Math.exp(-e.deltaY*.001));},{passive:false});
 canvas.addEventListener('keydown',e=>{let used=true;auto=false;motion();switch(e.key){case'ArrowLeft':yaw-=.12;break;case'ArrowRight':yaw+=.12;break;case'ArrowUp':pitch-=.12;break;case'ArrowDown':pitch+=.12;break;case'+':case'=':setZoom(zoom*1.1);break;case'-':setZoom(zoom/1.1);break;default:used=false;}if(used){e.preventDefault();schedule();}});
 canvas.addEventListener('pointerdown',e=>{auto=false;motion();pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,moved:false};if(pointers.size===2){const [a,b]=[...pointers.values()];pinch=Math.hypot(a.x-b.x,a.y-b.y);}});
 canvas.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;const old=pointers.get(e.pointerId);pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(pointers.size===2){const [a,b]=[...pointers.values()],next=Math.hypot(a.x-b.x,a.y-b.y);if(pinch>1)setZoom(zoom*next/pinch);pinch=next;drag.moved=true;}else{const dx=e.clientX-old.x,dy=e.clientY-old.y;yaw+=dx*.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+dy*.008));if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>5)drag.moved=true;schedule();}});
 canvas.addEventListener('pointerup',e=>{const tap=pointers.size===1&&drag&&!drag.moved;pointers.delete(e.pointerId);if(tap){const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;const hit=projected.filter(q=>matches(q.p)).map(q=>({q,d:Math.hypot(q.x-x,q.y-y)})).filter(q=>q.d<12).sort((a,b)=>a.d-b.d)[0];if(hit)choose(hit.q.p.id);}if(!pointers.size)drag=null;});
 canvas.addEventListener('lostpointercapture',e=>{pointers.delete(e.pointerId);if(!pointers.size)drag=null;});
 canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);drag=null;});
 $('#map3dSource').onclick=async()=>{const p=selected,owner=space,serial=request,loadId=++sourceSequence;if(!p?.docId.startsWith('brain:'))return;const dialog=$('#map3dSourceDialog');$('#map3dSourceTitle').textContent=p.title;$('#map3dSourceBody').textContent='Chargement de la source…';$('#map3dSourceMeta').textContent=p.source;dialog.showModal();try{const r=await fetch('/api/jarvis/doc?space='+encodeURIComponent(p.space)+'&id='+encodeURIComponent(p.docId.slice(6)));const data=await r.json();if(!r.ok)throw Error('Cette source n’est plus disponible.');if($('#spaceSelect').value!==owner||serial!==request||loadId!==sourceSequence||!dialog.open)return;$('#map3dSourceBody').textContent=data.body;}catch{if(loadId===sourceSequence)$('#map3dSourceBody').textContent='Source indisponible. Actualise la carte.';}};
 $('#map3dSourceClose').onclick=()=>$('#map3dSourceDialog').close();$('#map3dSourceDialog').addEventListener('close',()=>sourceSequence++);
 document.addEventListener('jarvis:view',e=>{if(e.detail.view==='memory3d'){resize();load(true);}else{cancelAnimationFrame(frame);frame=0;}});
 document.addEventListener('jarvis:spacechange',()=>{sourceSequence++;request++;abort?.abort();points=[];loadedSpace='';loading=false;choose('');options();$('#map3dSourceDialog').close();$('#map3dSourceBody').textContent='';$('#map3dSourceTitle').textContent='';$('#map3dSourceMeta').textContent='';setTimeout(()=>{if(active())load(true);},0);});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else schedule();});
 reduced.addEventListener('change',()=>{auto=!reduced.matches;motion();schedule();});
 new ResizeObserver(resize).observe(canvas);motion();if(!section.hidden){resize();load();}
})();
