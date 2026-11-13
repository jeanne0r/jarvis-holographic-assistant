// Learn from direct user corrections, never from model assertions or retrieved text.
import {haTermsMatch} from './ha-search.mjs';
const normalize=s=>String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
const stop=new Set('de du des le la les l d un une en et est que qui quoi quel quelle quelles quels il elle je tu nous vous ce cette ces pour dans sur avec moi toi mon ma mes ton ta tes pas non plus bien toujours reponds reponse reponses'.split(' '));
const words=s=>normalize(s).split(' ').filter(w=>w.length>2&&!stop.has(w));
const secret=/password|mot de passe|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer\s|oauth|private.key|\b(?:sk-|ghp_|AIza)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_.-]{20,}/i;
export function relevantFacts(question,rows,space){
 const chosen=new Map();for(const row of rows){const previous=chosen.get(row.key);if(!previous||row.space===space&&previous.space!==space)chosen.set(row.key,row)}
 const terms=words(question),rank=row=>{
  const label=words(row.label),fact=words(row.fact);let score=0;
  for(const term of terms){if(haTermsMatch([term],label.join(' ')))score+=3;else if(haTermsMatch([term],fact.join(' ')))score++;}
  if(row.correctionKind==='preference')score+=2;
  return score;
 };
 let size=0;return [...chosen.values()].map(row=>({row,score:rank(row)})).filter(r=>r.score>0).sort((a,b)=>b.score-a.score||b.row.updated-a.row.updated).slice(0,4).flatMap(({row})=>{const item={key:row.key,label:row.label,fact:row.fact,entity_id:row.entity_id||null,source:row.origin||'mémoire explicite',kind:row.correctionKind||'fact'};const length=JSON.stringify(item).length;if(size+length>2400)return [];size+=length;return [item]});
}
export function validatedCorrections(question,candidates,observations){
 if(!Array.isArray(candidates)||secret.test(question))return [];
 const allowed=new Set(observations.flatMap(o=>o.result?.connected?o.result.states?.map(s=>s.entity_id)||[]:[]));
 return candidates.slice(0,3).filter(c=>{
  if(!c||!['identity','preference','rule'].includes(c.kind)||typeof c.key!=='string'||c.key.length<1||c.key.length>120||typeof c.fact!=='string'||c.fact.length<1||c.fact.length>800||typeof c.evidence!=='string'||c.evidence.length<8||c.evidence.length>400||!question.includes(c.evidence))return false;
  const text=c.key+' '+c.fact+' '+c.evidence;
  if(/autorisation|permission|privil[eè]ge|sans (?:confirmation|validation)|ignor.{0,30}(?:r[eè]gle|consigne|s[eé]curit[eé])|d[eé]sactiv.{0,30}(?:contr[oô]le|protection|s[eé]curit[eé])/i.test(c.fact))return false;
  if(secret.test(text)||/https?:\/\/|```|\b(?:sudo|curl|wget|eval|exec)\b/i.test(c.fact))return false;
  // The user must correct an interpretation, or clearly state a durable preference.
  if(!/\bnon\b|corrig|rectifi|en fait|plut[oô]t|d[eé]sormais|je (?:veux|pr[eé]f[eè]re)|quand je dis|ne .{0,30}pas|toujours|au lieu/i.test(c.evidence))return false;
  // Current readings are not durable knowledge. Explicit preference facts remain textual.
  if(/\d[\d.,]*\s*(?:°\s*c|[kmg]?w(?:h)?\b|%)/i.test(c.fact)&&!(c.kind==='preference'&&/pr[eé]f[eè]r|confort|consigne|temp[eé]rature (?:souhait[eé]e|cible)/i.test(c.evidence)))return false;
  if(c.entity_id&&!allowed.has(c.entity_id))return false;
  const factEntities=c.fact.match(/\b[a-z_]+\.[a-z0-9_]+\b/g)||[];
  if(factEntities.some(id=>!allowed.has(id)))return false;
  return words(c.fact).some(term=>haTermsMatch([term],words(c.evidence).join(' ')));
 }).map(({key,fact,kind,evidence,entity_id})=>({key:key.trim(),fact:fact.trim(),kind,evidence,entity_id:entity_id||''}));
}
export async function saveCorrections(question,candidates,observations,space,store){
 const valid=validatedCorrections(question,candidates,observations);let saved=0,failed=0;const applied=[];
 for(const c of valid){try{const result=await store('save_correction',{...c,space});result.saved?(saved++,applied.push({key:c.key,kind:c.kind,entity_id:c.entity_id})):failed++}catch{failed++}}
 return {saved,failed,applied};
}

export function correctedHintKeys(corrections,hints){
 return hints.filter(h=>corrections.some(c=>c.entity_id&&haTermsMatch(words(h.query),normalize(c.key))&&h.entities.some(e=>e.entity_id!==c.entity_id))).map(h=>h.key);
}
