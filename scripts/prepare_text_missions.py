"""C: one frontend asset derived from verified Lot A, no SSO/private release update."""
import argparse,hashlib,json
from pathlib import Path
from .prepare_embedded_panel import ROOT,replace_once


def prepare(destination):
    dest=Path(destination)
    if dest.exists():raise FileExistsError('Never overwrite a candidate or evidence')
    active=Path('/home/user/gateway/public/jarvis/hermes-embedded.js')
    historical=json.loads((ROOT/'docs/JARVIS_2_BIG_BOSS_LOT_A_RESULTS.json').read_text())
    row=next(r for r in historical['files'] if r['target']==str(active))
    raw=active.read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
    if active.is_symlink() or sha(raw)!=row['after_sha256']:raise PermissionError('Deployed Lot A preimage mismatch')
    source=raw.decode()
    old=" const submit=make('button','Soumettre cette demande',content);submit.type='button';submit.hidden=true;let textKey=null;"
    new=""" const consentLabel=make('label',null,content);consentLabel.id='hermesTextConsentLabel';consentLabel.hidden=true;
 const consent=make('input',null,consentLabel);consent.id='hermesTextConsent';consent.type='checkbox';consentLabel.append(document.createTextNode('Je confirme : demande de test synthétique uniquement, sans donnée personnelle. J’autorise son enregistrement et son traitement par Hermes.'));
 const textHelp=make('p','Décris une analyse de données fictives. Aucun fichier privé, shell, équipement ou publication. Envoi possible uniquement pendant une fenêtre autorisée ; sinon, prépare ton texte sans le transmettre.',consentLabel);
 const submit=make('button','Soumettre cette demande',content);submit.type='button';submit.hidden=true;let textKey=null,textAttempt=null,textBusy=false,textSubmissionEnabled=false;
 function textReady(){consentLabel.hidden=objective.hidden;consent.disabled=textBusy;objective.disabled=textBusy||textAttempt!==null;submit.disabled=!textSubmissionEnabled||!admissionsEnabled||!identity?.roles.includes('missions.create')||textBusy||!consent.checked||!(textAttempt?.objective||objective.value).trim()||objective.value.length>2000}
 objective.addEventListener('input',textReady);consent.addEventListener('change',textReady);
"""
    source=replace_once(source,old,new)
    old=" submit.onclick=async()=>{if(!objective.value.trim()||objective.value.length>2000)return;submit.disabled=true;textKey??=crypto.randomUUID();try{await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':textKey},body:JSON.stringify({objective:objective.value})});textKey=null;objective.value='';await refreshList()}catch(e){status.textContent=e.message+' Consulte l’historique avant de réessayer.'}finally{submit.disabled=false}};"
    new=""" submit.onclick=async()=>{
  if(!textSubmissionEnabled||textBusy||!consent.checked||objective.hidden||!admissionsEnabled||!identity?.roles.includes('missions.create'))return;
  if(!textAttempt){if(!objective.value.trim()||objective.value.length>2000)return;textAttempt={key:crypto.randomUUID(),objective:objective.value}}
  const attempt=textAttempt;textBusy=true;textReady();
  try{const result=await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':attempt.key},body:JSON.stringify({objective:attempt.objective})});
   if(typeof result.mission_id!=='string')throw Error('Admission non confirmée');
   selected=result.mission_id;textAttempt=null;objective.value='';consent.checked=false;submit.textContent='Soumettre cette demande';await refreshList();
  }catch(e){consent.checked=false;submit.textContent='Réessayer la même demande';status.textContent=e.message+' Vérifie l’historique. Un nouvel envoi conservera exactement la même demande et sa clé.'}
  finally{textBusy=false;textReady()}
 };"""
    source=replace_once(source,old,new)
    # Keep existing flag/role decisions; the new consent follows their visibility.
    needle="objective.hidden=submit.hidden=!(config.textEnabled===true&&admissionsEnabled&&identity.roles.includes('missions.create'));"
    if source.count(needle)!=2:raise PermissionError('Flag visibility drift')
    source=source.replace(needle,"textSubmissionEnabled=config.textEnabled===true;objective.hidden=submit.hidden=!(config.readEnabled===true&&identity.roles.includes('missions.read'));textReady();")
    source=replace_once(source,"create.disabled=true;objective.hidden=submit.hidden=true;globalThis", "create.disabled=true;objective.hidden=submit.hidden=true;textReady();globalThis")
    source=replace_once(source,"objective.value='';objective.hidden=submit.hidden=true;clearInterval(timer)","objective.value='';textAttempt=null;consent.checked=false;objective.hidden=submit.hidden=true;textReady();clearInterval(timer)")
    installed=Path('/opt/jarvis-hermes-pilot')
    known=json.loads((installed/'deployment-files.json').read_text())
    for name,digest in known.items():
        p=installed/name
        if p.is_symlink() or not p.resolve().is_relative_to(installed.resolve()) or sha(p.read_bytes())!=digest:raise PermissionError('Installed release drift')
    # C MUST NOT incorporate the optional SSO code from the development worktree.
    api=(installed/'hermes-embedded-api.mjs').read_text()
    if 'delegationVerifier' in api or "features.textEnabled===true" not in api or "['memory.search','report']" not in api:raise PermissionError('Existing private-cookie text contract not found')
    dest.mkdir(parents=True)
    (dest/'hermes-embedded.js').write_text(source)
    (dest/'hermes-embedded.js.before').write_bytes(raw)
    result={'lot':'C','production_modified':False,'sso_dependency':False,'gateway_restart':False,'private_release_changed':False,
      'files':[{'target':str(active),'before_sha256':sha(raw),'after_sha256':sha(source.encode()),'artifact':'hermes-embedded.js','backup':'hermes-embedded.js.before'}],
      'installed_release_manifest_sha256':sha((installed/'deployment-files.json').read_bytes()),
      'requires_separate_approval':['frontend asset installation','bounded text admission and private service restart','Windows/GPU execution window'],
      'all_runtime_flags_unchanged':True}
    (dest/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');args=p.parse_args();print(json.dumps(prepare(args.destination)))
