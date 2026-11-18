from pathlib import Path
import sqlite3
r=Path(__file__).parent
with sqlite3.connect(r/'data/brain.sqlite') as db, sqlite3.connect(r/'data/before-spaces.sqlite') as backup:db.backup(backup)
p=r/'store.py';s=p.read_text();pos=s.index('TOPICS=');s=s[:pos]+'''SPACES={'user':'User','amelie':'Amélie','commun':'Commun'}
DB.execute('BEGIN IMMEDIATE')
if 'space' not in {row[1] for row in DB.execute('PRAGMA table_info(docs)')}:
 DB.execute("ALTER TABLE docs ADD COLUMN space TEXT NOT NULL DEFAULT 'user'")
 DB.execute('CREATE INDEX idx_docs_space_updated ON docs(space,updated)')
DB.commit()
def space_id(value):
 if not isinstance(value,str) or value not in SPACES:raise ValueError('Espace inconnu.')
 return value
''' + s[pos:]
s=s.replace("SELECT fingerprint FROM docs WHERE id=?","SELECT fingerprint,space FROM docs WHERE id=?")
s=s.replace("DB.execute('INSERT OR REPLACE INTO docs VALUES(?,?,?,?,?,?,?,?,?)'", "DB.execute('INSERT OR REPLACE INTO docs(id,title,body,kind,topic,status,source,updated,fingerprint,space) VALUES(?,?,?,?,?,?,?,?,?,?)'")
s=s.replace("d.get('fingerprint')))", "d.get('fingerprint'),old['space'] if old else d.get('space','user')))")
s=s.replace("def listing(q=''):","def listing(q='',space='user'):")
s=s.replace('WHERE search MATCH ? ORDER BY','WHERE search MATCH ? AND d.space=? ORDER BY').replace('(match,)).fetchall()', '(match,space)).fetchall()')
s=s.replace("FROM docs ORDER BY updated DESC LIMIT 1200').fetchall()", "FROM docs WHERE space=? ORDER BY updated DESC LIMIT 1200',(space,)).fetchall()")
s=s.replace('def import_chats(raw):','def import_chats(raw,space=\'user\'):')
s=s.replace("id='chatgpt:'+cid,title=", "id=('chatgpt:' if space=='user' else 'chatgpt:'+space+':')+cid,space=space,title=")
s=s.replace("return import_chats(sys.stdin.buffer.read())", "return import_chats(sys.stdin.buffer.read(),space_id(sys.argv[2] if len(sys.argv)>2 else 'user'))")
s=s.replace("if action=='list':", "space=space_id(a.get('space','user'))\n if action=='list':")
s=s.replace("docs=listing(a.get('q','')),total=DB.execute('SELECT count(*) FROM docs').fetchone()[0],counts={r[0]:r[1] for r in DB.execute('SELECT kind,count(*) FROM docs GROUP BY kind')}","docs=listing(a.get('q',''),space),total=DB.execute('SELECT count(*) FROM docs WHERE space=?',(space,)).fetchone()[0],counts={r[0]:r[1] for r in DB.execute('SELECT kind,count(*) FROM docs WHERE space=? GROUP BY kind',(space,))}")
s=s.replace("SELECT * FROM docs WHERE id=?',(a['id'],)","SELECT * FROM docs WHERE id=? AND space=?',(a['id'],space)")
s=s.replace("if action=='save':", "if action=='move':\n  target=space_id(a.get('target'))\n  changed=DB.execute('UPDATE docs SET space=? WHERE id=? AND space=?',(target,a.get('id'),space)).rowcount\n  if not changed:raise ValueError('Souvenir introuvable dans cet espace.')\n  DB.commit();return {'moved':True,'space':target}\n if action=='save':")
s=s.replace("d=dict(id='note:'+os.urandom(12).hex(),title=", "d=dict(id='note:'+os.urandom(12).hex(),space=space,title=")
p.write_text(s)
p=r/'backend.mjs';s=p.read_text().replace('store(action,data={})','store(action,data={},space=\'user\')').replace("[ROOT+'/store.py',action]","[ROOT+'/store.py',action,space]")
s=s.replace("if(action==='docs'", "const space=url.searchParams.get('space')||'user';\n if(!['user','amelie','commun'].includes(space))return json(res,400,{error:'Espace inconnu.'});\n if(action==='move'&&req.method==='POST')return json(res,200,await store('move',{...JSON.parse((await body(req)).toString()),space}));\n if(action==='docs'")
s=s.replace("{q:url.searchParams.get('q')||''}","{q:url.searchParams.get('q')||'',space}").replace("{id:url.searchParams.get('id')}","{id:url.searchParams.get('id'),space}")
s=s.replace("store('save',JSON.parse((await body(req)).toString()))", "store('save',{...JSON.parse((await body(req)).toString()),space}))")
s=s.replace("store('import',await body(req,150*1024*1024))","store('import',await body(req,150*1024*1024),space)")
s=s.replace("{q:query}","{q:query,space}").replace("{id:item.id}","{id:item.id,space}")
p.write_text(s)
p=r/'public/index.html';s=p.read_text();s=s.replace('<div class="rail-label">ESPACE PERSONNEL</div>','<div class="rail-label">ESPACE PERSONNEL</div>')
s=s.replace('<div class="breadcrumb">ESPACE PERSONNEL <span>/</span>', '<div class="breadcrumb"><label for="spaceSelect">ESPACE PERSONNEL</label><select id="spaceSelect" aria-label="Choisir une personne"><option value="user">User</option><option value="amelie">Amélie</option><option value="commun">Commun</option></select><span>/</span>')
s=s.replace('<div>User<small>', '<div><span id="profileName">User</span><small>')
s=s.replace('<h3>Dans le même univers</h3>', '<form id="moveForm" class="move-form"><label for="moveTarget">Classer dans l’espace</label><select id="moveTarget"><option value="user">User</option><option value="amelie">Amélie</option><option value="commun">Commun</option></select><button type="submit" class="outline">Déplacer ce souvenir</button><p id="moveError" class="error"></p></form><h3>Dans le même univers</h3>')
s=s.replace('Conversations présentes sur cette machine, y compris les archives.', 'Les nouvelles conversations de cette machine arrivent dans l’espace User. Tu peux ensuite les déplacer vers Amélie ou Commun.')
s=s.replace('Réponses via Codex · seuls', 'Jarvis consulte uniquement l’espace sélectionné. Réponses via Codex · seuls')
p.write_text(s)
p=r/'public/app.js';s=p.read_text();s=s.replace("let docs=[]", "const spaces={user:'User',amelie:'Amélie',commun:'Commun'};\nlet currentSpace='user',detailId=null;\ntry{currentSpace=localStorage.getItem('jarvis-space')||'user'}catch{}\nif(!spaces[currentSpace])currentSpace='user';\nlet docs=[]")
s=s.replace("fetch('/api/jarvis/'+path,options)","fetch('/api/jarvis/'+path+(path.includes('?')?'&':'?')+'space='+encodeURIComponent(currentSpace),options)")
s=s.replace("async function openDoc(id){try{", "async function openDoc(id){const requestedSpace=currentSpace;try{")
s=s.replace("$('#detailKind').textContent=d.kind", "if(requestedSpace!==currentSpace)return;detailId=id;$('#moveTarget').value=currentSpace;$('#moveError').textContent='';$('#detailKind').textContent=d.kind")
s=s.replace("const q=$('#question').value.trim();if(!q)return;", "const q=$('#question').value.trim();if(!q)return;const askSpace=currentSpace;")
s=s.replace("const r=await post('ask',{question:q});pending", "const r=await post('ask',{question:q});if(askSpace!==currentSpace)return;pending")
s=s.replace("load();setInterval", """function spaceLabels(){
 $('#spaceSelect').value=currentSpace;$('#profileName').textContent=spaces[currentSpace];$('.avatar').textContent=spaces[currentSpace][0];
 $('#importBtn').title='Importer les conversations dans l’espace '+spaces[currentSpace];
 $('#noteDialog h2').textContent='Une idée pour '+spaces[currentSpace]+'.';
}
$('#spaceSelect').onchange=async e=>{
 currentSpace=e.target.value;try{localStorage.setItem('jarvis-space',currentSpace)}catch{}
 ++loadSequence;docs=[];allDocs=[];activeTopic='';$('#search').value='';$('#messages').replaceChildren();$('#question').value='';$('#notice').hidden=true;
 $('#count').textContent='—';$('#navCount').textContent='0';$('#noteForm').reset();zoom=1;pan={x:0,y:0};spaceLabels();render();await load();
};
$('#moveForm').onsubmit=async e=>{e.preventDefault();const target=$('#moveTarget').value;const b=$('#moveForm button');b.disabled=true;try{await post('move',{id:detailId,target});$('#detail').close();await load();notify('Souvenir classé dans l’espace '+spaces[target]+'.')}catch(e){$('#moveError').textContent=e.message}finally{b.disabled=false}};
spaceLabels();load();setInterval""")
p.write_text(s)
p=r/'public/style.css';s=p.read_text()+'''\n.breadcrumb{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.breadcrumb label{font-size:10px}#spaceSelect{background:#13232c;color:var(--mint);padding:7px 28px 7px 11px;font-size:15px;max-width:145px}.breadcrumb>span{margin:0 3px}.move-form{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:20px}.move-form label{margin-bottom:5px}.move-form select{margin-bottom:12px}header{gap:12px}@media(max-width:760px){header{height:auto;min-height:80px;padding:12px 0}.breadcrumb{gap:5px}.breadcrumb label{width:100%;font-size:9px}.breadcrumb b{display:none}header>.primary{flex-shrink:0}.breadcrumb>span{display:none}#spaceSelect{font-size:15px;padding:6px 26px 6px 9px}}\n''';p.write_text(s)
