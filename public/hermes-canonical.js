// Inert formatter, not wired into the panel until server-bound metadata is reviewed.
// Never parse model text into authority or replace dates inside it.
(() => {
 function sections(modelOutput,projection){
  if(typeof modelOutput!=='string')throw Error('Model text required');
  const result={modelText:modelOutput,modelLabel:'Réponse du modèle — non vérifiée',metadataText:null};
  if(projection===undefined||projection===null)return result;
  if(projection.schema!=='canonical_metadata.v1'||projection.origin!=='sqlite'||!Array.isArray(projection.items)||projection.items.length>200)throw Error('Canonical projection required');
  const lines=['Métadonnées issues de SQLite — horodatages UTC'];
  for(const row of projection.items){
   for(const key of ['memory_id','revision_id','source_ref','stored_validation_status','revision_status','observed_utc'])if(typeof row[key]!=='string')throw Error('Canonical field required');
   lines.push('Source : '+row.source_ref,'Mémoire : '+row.memory_id+' · Révision : '+row.revision_id,
    'Observation UTC : '+row.observed_utc,'État de révision : '+row.revision_status+' · Validation enregistrée : '+row.stored_validation_status,
    'Début de validité UTC : '+(row.valid_from_utc??'non précisé'),'Fin de validité UTC : '+(row.valid_to_utc??'non précisée'),'');
  }
  result.metadataText=lines.join('\n');return result;
 }
 globalThis.JarvisCanonical=Object.freeze({sections});
})();
