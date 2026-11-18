"""Deterministic local C2 review. Private content never reaches stdout or a model."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

QUERY='S19* AND (Hydro OR refroidissement)'
WORDS=re.compile(r's19|antminer|hydro|refroid|pompe|échangeur|radiateur|débit|pression|températ|erreur|remplac|corrig|install|mesur',re.I)
SECRET_LINE=re.compile(r'password|mot de passe|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|bearer\s|BEGIN .*PRIVATE KEY',re.I)
SECRET_VALUE=re.compile(r'AIza[\w-]{20,}|\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]+|eyJ[\w.-]{20,})\b')
MEASURE=re.compile(r'(?<!\w)(-?\d+(?:[.,]\d+)?)\s*(°C|[lL]/(?:min|h)|bar|kPa|kW|W|mm)\b')


def exclusive(path,value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())


def redact(text):
    return '\n'.join('[sensitive line withheld]' if SECRET_LINE.search(line) else SECRET_VALUE.sub('[sensitive value withheld]',line) for line in text.splitlines())


def inspect(row):
    text=row['body'];lines=text.splitlines();chosen=set()
    for i,line in enumerate(lines):
        if WORDS.search(line):chosen.update(range(max(0,i-1),min(len(lines),i+2)))
        if len(chosen)>=36:break
    excerpts=[]
    for i in sorted(chosen)[:36]:
        line=redact(lines[i]);excerpts.append({'line':i+1,'text':line[:900],'line_truncated':len(line)>900})
    rendered='\n'.join(x['text'] for x in excerpts)
    measures=[{'raw_value':v,'raw_unit':unit,'validation':'unverified_source_statement'} for v,unit in MEASURE.findall(rendered)]
    administrative=bool(re.search(r'JARVIS\s*2[.,]0|Mission Codex|PHASE\s+[345]',text,re.I))
    return {'reference':{'source_db':'brain.sqlite','table':'docs','id':row['id'],'space':row['space'],
                         'source_reference':redact(row['source']),'kind':row['kind']},
            'title':redact(row['title']),'document_updated_at':row['updated'],
            'observation_time':None,'observation_time_reason':'Document timestamp is not proof of measurement time',
            'body_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'source_fingerprint':row['fingerprint'],'original_speaker':'not_determined',
            'review_state':'possible_meta_project_instructions' if administrative else 'candidate_for_human_review',
            'excerpts':excerpts,'measurements_to_review':measures,
            'correction_signals':bool(re.search(r'corrig|remplac|finalement|erreur|en fait',rendered,re.I)),
            'installation_signals':bool(re.search(r'install|monté|branché|utilis',rendered,re.I)),
            'date_tokens_to_review':sorted(set(re.findall(r'\b20\d\d[-/]\d\d[-/]\d\d\b',rendered))),
            'proposed_status':'inferred','canonical_write_authorized':False,
            'privacy_note':'Derived excerpts redacted; original database unchanged; hashes refer to original text'}


def review(database,folder,*,scope='user',limit=20):
    if type(limit) is not int or not 1<=limit<=20 or scope!='user':raise ValueError('Approved single-owner twenty-source bound')
    folder=Path(folder);folder.mkdir(mode=0o700,parents=True,exist_ok=False);folder.chmod(0o700)
    c=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    c.execute('PRAGMA query_only=ON');c.execute('PRAGMA temp_store=MEMORY');c.execute('BEGIN')
    try:
        # Only IDs/metadata come from the search index; source bodies are read only
        # after reserving the bounded selection. No snippets/highlight/index dump.
        selected=list(c.execute('''SELECT d.id,d.kind FROM search JOIN docs d ON d.id=search.id
          WHERE search MATCH ? AND d.space=? ORDER BY
          CASE d.kind WHEN 'ChatGPT' THEN 0 WHEN 'Jarvis' THEN 1 WHEN 'Mémoire' THEN 2 ELSE 3 END,
          bm25(search),d.updated DESC LIMIT ?''',(QUERY,scope,limit)))
        if any(r['kind'] in {'ChatGPT','Codex','Jarvis'} for r in selected):
            raise PermissionError('Conversation documents require explicit turn-level selection before body reads')
        ids=list(dict.fromkeys(r['id'] for r in selected))
        exclusive(folder/'selected-references.json',{'reserved_source_ids':ids,'maximum_source_reads':limit,'scope':scope,'query':QUERY})
        sources=[]
        for ident in ids:
            row=c.execute('SELECT id,title,body,kind,source,updated,fingerprint,space FROM docs WHERE id=? AND space=?',(ident,scope)).fetchone()
            if row:sources.append(inspect(dict(row)))
        groups={}
        for i,source in enumerate(sources):
            for m in source['measurements_to_review']:groups.setdefault(m['raw_unit'],{}).setdefault(m['raw_value'],set()).add(i+1)
        divergences=[{'unit':unit,'values':{v:sorted(refs) for v,refs in values.items()},
                      'interpretation':'Different values may be different conditions/times; no automatic contradiction or resolution'}
                     for unit,values in groups.items() if len(values)>1]
        report={'mode':'private-dry-run','created_at':time.time(),'project':'Antminer S19 XP Hydro — refroidissement',
                'selected_sources':len(ids),'examined_sources':len(sources),'sources':sources,
                'measurement_divergences_to_review':divergences,
                'current_configuration':'Not established automatically; inspect original sources and validate provenance',
                'original_dates_preserved':True,'source_observations_independently_verified':False,
                'writes_to_source_databases':0,'model_calls':0,'windows_transmissions':0,'index_writes':0,
                'candidate_publications':0,'requires_human_review':True}
        exclusive(folder/'import-review.json',report)
        return {'examined_sources':len(sources),'candidate_sources':sum(s['review_state']=='candidate_for_human_review' for s in sources),
                'sources_flagged_for_exclusion':sum(s['review_state']!='candidate_for_human_review' for s in sources),
                'sources_with_correction_signals':sum(s['correction_signals'] for s in sources),
                'measurement_statement_count':sum(len(s['measurements_to_review']) for s in sources),
                'unit_groups_requiring_review':len(divergences),'source_database_writes':0,
                'private_report':str(folder/'import-review.json'),'content_sent_to_models':False,'index_writes':0}
    finally:c.rollback();c.close()


def review_selected_turns(database, references, folder):
    """PREPARED ONLY: explicit normalized turn references, no automatic discovery.

    One source is exactly a user/assistant pair at a known revision. This is not
    run on real data by the exhausted C2 authorization.
    """
    if not isinstance(references,list) or not 1<=len(references)<=20:
        raise ValueError('At most twenty explicitly reviewed turn references')
    keys=[]
    for ref in references:
        if not isinstance(ref,dict) or set(ref)!={'session_id','turn','revision'} or not isinstance(ref['session_id'],str) or not ref['session_id'] or type(ref['turn']) is not int or type(ref['revision']) is not int or ref['turn']<0 or ref['revision']<1:
            raise ValueError('Exact stable session/turn/revision required')
        keys.append((ref['session_id'],ref['turn'],ref['revision']))
    if len({(s,t) for s,t,_ in keys})!=len(keys):raise ValueError('Distinct turn sources required; no alternate revisions of the same turn')
    folder=Path(folder);folder.mkdir(mode=0o700,parents=True,exist_ok=False);folder.chmod(0o700)
    exclusive(folder/'selected-turns.json',{'references':references,'maximum_source_reads':20})
    c=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
    try:
        # Validate the entire selection using metadata before projecting ANY body.
        # A stale/inaccessible later reference must not consume earlier contents.
        for session,turn,revision in keys:
            matches=c.execute("""SELECT count(*) FROM conversation_turns t
              JOIN conversation_sessions s ON s.id=t.session_id
              WHERE s.space='user' AND t.session_id=? AND t.turn=? AND t.revision=?""",(session,turn,revision)).fetchone()[0]
            if matches!=1:raise PermissionError('Turn revision missing, ambiguous or inaccessible')
        sources=[]
        for session,turn,revision in keys:
            row=c.execute("""SELECT t.user,t.assistant,t.updated FROM conversation_turns t
              JOIN conversation_sessions s ON s.id=t.session_id
              WHERE s.space='user' AND t.session_id=? AND t.turn=? AND t.revision=?""",(session,turn,revision)).fetchone()
            if not row:raise PermissionError('Turn revision missing or inaccessible')
            body='Toi: '+row['user']+'\nAssistant: '+row['assistant']
            record=inspect({'id':f'{session}:{turn}:r{revision}','space':'user','source':f'brain://turn/{session}/{turn}/{revision}',
                 'kind':'normalized_turn','title':'Explicitly selected turn','updated':row['updated'],'fingerprint':None,'body':body})
            record['reference']['table']='conversation_turns';record['exact_turn_reference']={'session_id':session,'turn':turn,'revision':revision}
            record['role_segments']={'user':'Toi:','assistant':'Assistant:'}
            sources.append(record)
        report={'mode':'private-turn-dry-run','examined_sources':len(sources),'sources':sources,'requires_human_review':True,
                'model_calls':0,'index_writes':0,'writes_to_source_databases':0}
        exclusive(folder/'import-review.json',report);return {'examined_turns':len(sources),'model_calls':0,'index_writes':0}
    finally:c.rollback();c.close()
