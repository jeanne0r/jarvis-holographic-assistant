// Deterministic local commands; all other requests still go to the language model.
export function quickReply(question){
 const q=question.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[’']/g,' ').replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();
 let answer,action=null;
 if(/^(salut|bonjour|bonsoir|coucou|hello)( jarvis)?( (tu es la|t es la|tu m entends))?$/.test(q)||/^(tu es la|t es la|tu m entends)( jarvis)?$/.test(q))answer='À ton service. Que puis-je faire pour toi ?';
 else if(/^(que peut on faire ici|qu est ce qu on peut faire ici|que peux tu faire|aide moi)$/.test(q))answer='On peut retrouver une discussion, garder une idée ou ouvrir une application de la maison. Dis-moi ce que tu veux faire ; je te guide.';
 else {
 const who=q.match(/^(?:c est|je suis|moi c est|passe (?:dans|sur) (?:l espace (?:de )?)?)(member1|member2|member3|member4|shared)$/)||q.match(/^(?:c est|je suis|moi c est) (member1|member2|member3|member4)$/);
 const app=q.match(/^(?:ouvre|lance)(?: moi)? (astro|allemand|verbes)(?: s il te plait| stp)?$/);
 if(who){answer='Je sélectionne cet espace.';action={type:'switch_space',target:who[1]};}
 else if(app){answer='J’ouvre cette application.';action={type:'open_app',target:app[1]};}
 }
 return answer?{answer,action,sourceIds:[],sources:[]}:null;
}
