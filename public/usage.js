(() => {
  const daily = document.querySelector('#voiceDailyCost');
  const balance = document.querySelector('#voiceCreditBalance');
  const note = document.querySelector('#voiceCostNote');
  const sync = document.querySelector('#voiceCostSync');
  const dialog = document.querySelector('#voiceBalanceDialog');
  const form = document.querySelector('#voiceBalanceForm');
  const storageKey = 'jarvis-voice-usage-pending-v1';
  let queue = [], sending = false, snapshot = null;
  try { queue = JSON.parse(localStorage.getItem(storageKey) || '[]'); } catch {}
  if (!Array.isArray(queue)) queue = [];
  queue = queue.filter(row => row && typeof row.sessionId === 'string' && Number.isInteger(row.sequence) && row.usage).slice(-1000);

  function money(amount, currency) {
    if (!Number.isFinite(amount)) return 'Indisponible';
    if (amount > 0 && amount < .0001) return '< 0,0001 ' + currency;
    return new Intl.NumberFormat('fr-FR', {style: 'currency', currency,
      minimumFractionDigits: 2, maximumFractionDigits: 4}).format(amount);
  }

  function paint(data) {
    snapshot = data;
    daily.textContent = data.todayUsd === null ? 'Suivi incomplet' : money(data.todayUsd, 'USD');
    const start = new Date(data.trackingSince);
    const todayStart = new Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/Zurich', year: 'numeric', month: '2-digit', day: '2-digit'}).format(start);
    document.querySelector('#voiceDailyScope').textContent = todayStart === data.day ?
      'Depuis ' + start.toLocaleTimeString('fr-CH', {timeZone: 'Europe/Zurich', hour: '2-digit', minute: '2-digit'}) + ' · USD' : 'Google · voix et outils · USD';
    balance.textContent = data.balance ? money(data.balance.remaining, data.balance.currency) : 'À renseigner';
    document.querySelector('#voiceBalanceEdit').textContent = data.balance ? 'Actualiser le solde' : 'Saisir le solde';
    const google = data.google || {state: 'not_connected', today: []};
    const age = Date.now() - Date.parse(google.checkedAt || '');
    const current = google.state === 'ready' && google.day === data.day && age < 45 * 60 * 1000;
    document.querySelector('#voiceGoogleCost').textContent = current ? google.today.map(row => money(row.amount, row.currency)).join(' + ') :
      ['pending_export', 'awaiting_today', 'export_updating'].includes(google.state) ? 'En attente de Google' : 'Non disponible';
    document.querySelector('#voiceGoogleStatus').textContent = current ?
      'Mis à jour à ' + new Date(google.checkedAt).toLocaleTimeString('fr-CH', {timeZone: 'Europe/Zurich', hour: '2-digit', minute: '2-digit'}) + ' · publication différée' : google.message || 'Connexion Google en préparation.';
    const since = new Date(data.trackingSince).toLocaleString('fr-CH', {timeZone: 'Europe/Zurich', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    const parts = ['Appels Google Jarvis · texte et voix · suivi depuis le ' + since + ' · journée en Suisse.'];
    if (data.balance) {
      const updated = new Date(data.balance.updatedAt).toLocaleString('fr-CH', {timeZone: 'Europe/Zurich', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
      if (data.balance.source === 'google-export-estimate') {
        const reference = new Date(data.balance.referenceAt).toLocaleString('fr-CH', {timeZone: 'Europe/Zurich', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
        parts.push('Référence : ' + money(data.balance.amount, data.balance.currency) + ' au ' + reference + ', moins les coûts Gemini API publiés ensuite par Google pour ce projet. Les coûts des autres services, comme BigQuery, sont exclus de cette déduction.');
        parts.push('Les périodes horaires chevauchant cette référence sont réparties au prorata. Les estimations de tokens ne sont pas déduites une seconde fois.');
      } else {
        parts.push('Solde saisi le ' + updated + ', diminué des coûts suivis ensuite.');
        if (data.balance.currency !== 'USD') parts.push('Conversion indicative BCE du ' + data.balance.fxDate + '.');
      }
    }
    const googleBalance = data.balance?.source === 'google-export-estimate';
    parts.push(googleBalance ? 'Recharges et dépenses hors de ce projet non synchronisées. Solde calculé, pas lu sur le portefeuille Google.' : 'Autres usages, recharges, taxes et remises non synchronisés.');
    const creditState = document.querySelector('#voiceCreditState');
    if (googleBalance) {
      creditState.textContent = data.balance.status === 'waiting_google' ? 'Base enregistrée · en attente des consommations Google' :
        data.balance.status === 'stale' ? 'Derniers coûts Google connus · actualisation en attente' :
        data.balance.status === 'currency_mismatch' ? 'Devise Google différente · calcul suspendu' :
        data.balance.status === 'scope_unknown' ? 'Service Google non identifié · calcul suspendu' :
        'Base − ' + money(data.balance.deducted, data.balance.currency) + ' de coûts Google publiés';
    } else creditState.textContent = data.balance ? 'Déduction selon les tokens estimés' : '';
    note.textContent = parts.join(' ');
    pendingStatus();
  }

  function pendingStatus(error = false) {
    sync.textContent = queue.length ? (error ? 'Connexion au suivi interrompue · ' : '') +
      queue.length + ' relevé(s) en attente, montants incomplets.' : 'Estimation aux tarifs publics payants · solde officiel sur Google.';
    sync.classList.toggle('error', Boolean(queue.length));
  }

  function saveQueue() {
    try { localStorage.setItem(storageKey, JSON.stringify(queue)); } catch {}
    pendingStatus();
  }

  async function refreshOpenAI() {
    const root=document.querySelector('#openaiUsage'), note=document.querySelector('#openaiUsageNote');
    const button=document.querySelector('#openaiUsageRefresh');button.disabled=true;
    try {
      const response=await fetch('/api/jarvis/openai/usage', {signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw Error();const data=await response.json();root.replaceChildren();
      const card=(title,value,description)=>{const el=document.createElement('div');el.className='voice-cost-card';for(const [tag,text] of [['small',title],['strong',value],['span',description]]){const part=document.createElement(tag);part.textContent=text;el.append(part)}root.append(el)};
      const date=value=>value?new Date(value).toLocaleString('fr-CH',{timeZone:'Europe/Zurich',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'non communiquée';
      for(const bucket of data.buckets||[]) {
        for(const w of [bucket.primary,bucket.secondary].filter(Boolean)) {
          const mins=w.windowDurationMins,label=mins===10080?'7 jours':mins===300?'5 heures':Number.isFinite(mins)?mins>=60?(mins/60)+' heures':mins+' minutes':'période OpenAI';
          card('Codex '+(bucket.plan||'')+' · '+label,Math.round(w.remainingPercent)+' % restants','Utilisé : '+w.usedPercent+' % · Réinitialisation : '+date(w.resetsAt));
        }
        if(bucket.credits)card('Crédits supplémentaires OpenAI',bucket.credits.unlimited?'Illimités':bucket.credits.balance!==null?bucket.credits.balance+' crédits':bucket.credits.hasCredits?'Disponibles':'Aucun','Distincts du quota inclus et des crédits Google.');
      }
      if(Number.isInteger(data.availableResets))card('Réinitialisations offertes',String(data.availableResets),'Disponibles sur le compte Codex · aucune activation automatique.');
      if(!data.buckets?.length)root.textContent='Quotas OpenAI indisponibles pour le moment.';
      note.textContent=(data.state==='stale'?'Dernier relevé connu · synchronisation interrompue. ':data.state==='ready'?'Données officielles OpenAI · ':'')+(data.checkedAt?'Relevé le '+date(data.checkedAt)+'. ':'')+'Quotas partagés avec les autres usages du même compte Codex. Le quota inclus ne correspond pas à un solde en dollars.';
    }catch{note.textContent='Impossible d’actualiser les quotas OpenAI. Réessaie dans un instant.';}finally{button.disabled=false;}
  }
  document.querySelector('#openaiUsageRefresh').addEventListener('click',refreshOpenAI);
  document.querySelector('#cockpitResources').addEventListener('click',refreshOpenAI);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refreshOpenAI()});
  setInterval(()=>{if(!document.hidden)void refreshOpenAI()},60000);
  void refreshOpenAI();

  async function refresh() {
    try {
      const response = await fetch('/api/jarvis/live/costs', {signal: AbortSignal.timeout(8000)});
      const data = await response.json();
      if (!response.ok) throw Error();
      paint(data);
    } catch {

      sync.textContent = 'Suivi des coûts indisponible. Les relevés restent en attente sur cet appareil.';
      sync.classList.add('error');
    }
  }

  async function flush() {
    if (sending || !queue.length) return;
    sending = true;
    try {
      while (queue.length) {
        const row = queue[0];
        const response = await fetch('/api/jarvis/live/usage', {
          method: 'POST', headers: {'content-type': 'application/json'},
          body: JSON.stringify(row), keepalive: true, signal: AbortSignal.timeout(10000),
        });
        const data = await response.json();
        if (!response.ok) throw Error();
        queue.shift();
        saveQueue();
        paint(data);
      }
    } catch { pendingStatus(true); }
    finally { sending = false; }
  }

  window.jarvisUsage = {
    record(sessionId, sequence, usage) {
      if (!sessionId) { sync.textContent = 'Recharge Jarvis pour activer le suivi de cette conversation.'; return; }
      if (!Number.isInteger(usage.promptTokenCount) || !Number.isInteger(usage.responseTokenCount)) return;
      // Persist only numeric usage, never audio, transcripts or Google tokens.
      const normalized = {};
      for (const name of ['promptTokenCount', 'responseTokenCount', 'thoughtsTokenCount'])
        if (Number.isInteger(usage[name])) normalized[name] = usage[name];
      for (const name of ['promptTokensDetails', 'responseTokensDetails'])
        if (Array.isArray(usage[name])) normalized[name] = usage[name].slice(0, 20).map(({modality, tokenCount}) => ({modality, tokenCount}));
      queue.push({sessionId, sequence, occurredAt: new Date().toISOString(), usage: normalized});
      saveQueue();
      void flush();
    },
  };

  document.querySelector('#voiceBalanceEdit').addEventListener('click', () => {
    form.elements.amount.value = snapshot?.balance?.remaining === null ? '' : snapshot?.balance?.remaining?.toFixed(4) || '';
    form.elements.currency.value = snapshot?.balance?.currency || 'USD';
    document.querySelector('#voiceBalanceError').textContent = '';
    dialog.showModal();
  });
  document.querySelector('#voiceBalanceClose').addEventListener('click', () => dialog.close());
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('[type=submit]');
    button.disabled = true;
    try {
      const response = await fetch('/api/jarvis/live/balance', {method: 'POST',
        headers: {'content-type': 'application/json'}, body: JSON.stringify({
          amount: Number(form.elements.amount.value), currency: form.elements.currency.value,
          deductionSource: snapshot?.balance?.deductionSource || 'local-estimate',
        })});
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Solde non enregistré.');
      paint(data);
      dialog.close();
    } catch (error) { document.querySelector('#voiceBalanceError').textContent = error.message; }
    finally { button.disabled = false; }
  });

  window.addEventListener('online', () => { void flush(); void refresh(); });
  window.addEventListener('pagehide', () => {
    for (const row of queue.slice(0, 8)) {
      navigator.sendBeacon('/api/jarvis/live/usage', new Blob([JSON.stringify(row)], {type: 'application/json'}));
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { void flush(); void refresh(); }
  });
  setInterval(() => { if (!document.hidden) { void flush(); void refresh(); } }, 15000);
  void refresh();
  void flush();
})();
