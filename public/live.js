(() => {
  const button = document.querySelector('#liveButton');
  const status = document.querySelector('#liveStatus');
  const stopButton = document.querySelector('#voiceStop');
  const clock = document.querySelector('#liveClock');
  const httpsLink = document.querySelector('#liveHttps');
  let active = null;
  const monitor=new JarvisLiveState(data=>{
    if(document.body.dataset.voice!==data.state)voiceState(data.state);
    document.dispatchEvent(new CustomEvent('jarvis:live-diagnostics',{detail:data}));
    document.dispatchEvent(new CustomEvent('jarvis:audio-level',{detail:{input:data.inputRms,output:data.outputRms,source:'rendered-pcm'}}));
  });
  Object.defineProperty(window,'jarvisLiveDiagnostics',{get:()=>monitor.snapshot()});
  monitor.publish(true);

  async function refreshMemoryStatus() {
    if (document.hidden) return;
    const label = document.querySelector('#voiceMemoryStatus');
    if (!label) return;
    try {
      const response = await fetch('/api/jarvis/memory/status?space=' + encodeURIComponent(document.querySelector('#spaceSelect').value));
      if (!response.ok) throw Error();
      const data = await response.json();
      const index = data.index;
      const progress = document.querySelector('#memoryProgress');
      if (progress) {
        progress.hidden = index.state !== 'indexing' || !index.total;
        progress.max = Math.max(1, index.total);
        progress.value = index.done;
      }
      label.textContent = `Mémoire durable active · ${data.savedFacts} fait${data.savedFacts === 1 ? '' : 's'} retenu${data.savedFacts === 1 ? '' : 's'}` +
        (index.state === 'ready' ? ' · Recherche dans les conversations prête.' : index.state === 'indexing' ? ` · Préparation des conversations : ${index.done}/${index.total}.` : ' · Recherche par mots disponible, recherche par sens en préparation.');
    } catch { label.textContent = 'État de la mémoire indisponible pour le moment.'; const progress = document.querySelector('#memoryProgress'); if (progress) progress.hidden = true; }
  }
  refreshMemoryStatus();
  setInterval(refreshMemoryStatus, 30000);
  document.addEventListener('jarvis:spacechange', refreshMemoryStatus);
  document.addEventListener('visibilitychange', refreshMemoryStatus);

  function flushTranscript(s, status = 'partial', end = false) {
    clearTimeout(s.archiveTimer);
    const row = s.archiveRow;
    if (row && (row.user || row.assistant) && s.usageSessionId) {
      window.jarvisArchive?.record({id:s.usageSessionId,space:s.space,channel:'voice',turn:s.archiveTurn,revision:++row.revision,user:row.user,assistant:row.assistant,status});
    }
    if (end) {if(row&&(row.user||row.assistant))document.dispatchEvent(new CustomEvent('jarvis:native-turn',{detail:{user:row.user,assistant:row.assistant,space:s.space}}));s.archiveTurn++;s.archiveRow={user:'',assistant:'',revision:0};document.querySelector('#liveTranscript').replaceChildren();}
  }
  function archiveTranscript(s, role, text) {
    if (!s.archiveRow) {s.archiveTurn=0;s.archiveRow={user:'',assistant:'',revision:0};}
    const field=role==='user'?'user':'assistant';
    for(let offset=0;offset<text.length;offset+=8000){
      const part=text.slice(offset,offset+8000);
      if(s.archiveRow.user.length+s.archiveRow.assistant.length+part.length>16000)flushTranscript(s,'continued',true);
      s.archiveRow[field]+=part;
    }
    clearTimeout(s.archiveTimer);s.archiveTimer=setTimeout(()=>flushTranscript(s),800);
  }

  function voiceState(state) {
    document.body.dataset.voice = state;
    document.dispatchEvent(new CustomEvent('jarvis:voice-state', {detail:{state}}));
  }

  function paint(text, error = false) {
    status.textContent = text;
    status.classList.toggle('error', error);
    const muted=Boolean(active?.muted);
    button.setAttribute('aria-label', !active?'Ouvrir le micro de Jarvis':muted?'Réactiver le micro de Jarvis':'Mettre le micro de Jarvis en pause');
    button.title=!active?'Ouvrir le micro':muted?'Réactiver le micro':'Mettre le micro en pause';
    button.setAttribute('aria-pressed',String(Boolean(active)&&!muted));button.classList.toggle('listening',Boolean(active)&&!muted);
    stopButton.hidden=!active;document.body.dataset.voiceMuted=String(muted);document.body.dataset.voiceSession=active?'active':'closed';document.dispatchEvent(new CustomEvent('jarvis:voice-controls'));
    const shortcut = document.querySelector('#hudMicShortcut');if (shortcut) shortcut.hidden = !active;
    if(error)monitor.stop(true);else if(!active)monitor.stop();
  }

  function toggleMute(){
    const s=active;if(!s)return;s.muted=!s.muted;s.lastSpeech=Date.now();
    if(s.muted&&s.gate?.active)send(s,{realtimeInput:{audioStreamEnd:true}});
    s.gate?.reset();for(const track of s.stream?.getAudioTracks()||[])track.enabled=!s.muted;
    paint(s.muted?'Micro en pause · la réponse continue.':'Je t’écoute. Tu peux m’interrompre en parlant.');monitor.mute(s.muted);
  }
  stopButton.addEventListener('click',()=>stop('Conversation vocale terminée. Le texte reste dans Conversation.'));

  function clearPlayback(s) {
    s.playbackEpoch=(s.playbackEpoch||0)+1;s.playback?.port.postMessage({type:'clear',epoch:s.playbackEpoch});monitor.clear();
    s.speaking = false;
  }

  function stop(text = 'Micro coupé.', error = false) {
    const s = active;
    active = null;
    if (s) {
      flushTranscript(s,s.archiveRow?.assistant?'interrupted':'complete',true);
      s.abort.abort();
      clearTimeout(s.timeout);
      clearInterval(s.ticker);
      clearPlayback(s);
      if (s.ws) { s.ws.onclose = null; s.ws.onerror = null; s.ws.close(); }
      s.stream?.getTracks().forEach(track => track.stop());
      s.mic?.disconnect();
      if (s.processor) { s.processor.port.onmessage = null; s.processor.disconnect(); }
      if (s.playback) { s.playback.port.onmessage = null; s.playback.disconnect(); }
      s.ctx?.close().catch(() => {});
    }
    clock.textContent = '';
    paint(text, error);
  }

  function send(s, message) {
    if (active !== s || s.ws?.readyState !== WebSocket.OPEN) return;
    s.ws.send(JSON.stringify(message));
  }

  function transcript(s, role, text) {
    if (!text) return;
    archiveTranscript(s,role,text);
    if(role==='model')document.dispatchEvent(new CustomEvent('jarvis:voice-caption',{detail:{text:(s.archiveRow?.assistant||text)}}));
    const panel = document.querySelector('#liveTranscript');
    if (!s.rows[role]) {
      const row = document.createElement('p');
      const label = document.createElement('strong');
      label.textContent = role === 'user' ? 'Toi · ' : 'Jarvis · ';
      const content = document.createElement('span');
      row.append(label, content);
      panel.append(row);
      s.rows[role] = content;
      while (panel.children.length > 16) panel.firstChild.remove();
    }
    s.rows[role].textContent += text;
    panel.scrollTop = panel.scrollHeight;
  }

  function play(s, inline) {
    if (active !== s || !inline.mimeType?.startsWith('audio/pcm') || !inline.data) return;
    const bytes = Uint8Array.from(atob(inline.data), c => c.charCodeAt(0));
    const count = Math.floor(bytes.length / 2);
    if (!count) return;
    const rate = Number(/rate=(\d+)/.exec(inline.mimeType)?.[1] || 24000);
    if (rate < 8000 || rate > 96000) return;
    const output = new Float32Array(count);
    const view = new DataView(bytes.buffer);
    for(let i=0;i<count;i++)output[i]=view.getInt16(i*2,true)/32768;
    s.receivingModelTurn=true;s.serverTurnComplete=false;s.turnAnswered=true;monitor.receivedAudio();
    s.playback.port.postMessage({type: 'audio', rate, samples: output}, [output.buffer]);
  }

  async function receive(s, event) {
    const raw = typeof event.data === 'string' ? event.data : await event.data.text();
    const data = JSON.parse(raw);
    if (data.usageMetadata) {
      // A metering/UI failure must never interrupt the voice conversation.
      try { window.jarvisUsage?.record(s.usageSessionId, ++s.usageSequence, data.usageMetadata); }
      catch { document.querySelector('#voiceCostSync').textContent = 'Un relevé de coût n’a pas pu être enregistré.'; }
    }
    if (active !== s) return;
    if (data.error) throw Error('Google a interrompu la session vocale. Vérifie le modèle et le quota Gemini.');
    if (data.setupComplete) {
      clearTimeout(s.timeout);
      s.ready = true;monitor.ready();
      const history=window.jarvisHistory?.()||[];
      if(history.length)send(s,{clientContent:{turns:history.map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:m.text}]})),turnComplete:false}});
      s.started = s.lastSpeech = Date.now();
      paint(s.muted?'Micro en pause · touche le cœur pour reprendre.':'Je t’écoute. Tu peux m’interrompre en parlant.');
      s.ticker = setInterval(() => {
        if (active !== s) return;
        const seconds = Math.max(0, s.maxSeconds - Math.floor((Date.now() - s.started) / 1000));
        clock.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
        if (!seconds) stop('Fin de l’essai de 10 minutes. Tu peux réouvrir le micro.');
        else if (Date.now() - s.lastSpeech > 120000 && !s.speaking)
          stop('Micro coupé après deux minutes sans parole.');
      }, 1000);
    }
    if (data.toolCallCancellation) {
      for (const id of data.toolCallCancellation.ids || []) s.cancelledTools.add(id);
    }
    if (data.toolCall) {
      s.awaitingToolAnswer=true;
      monitor.wait('outil Gemini');
      for (const call of (data.toolCall.functionCalls || []).slice(0, 4)) {
        // Keep incoming audio and interruption messages flowing during the lookup.
        void (async () => {
        let result;
        try {
          const response = await fetch('/api/jarvis/live/tool', {
            method: 'POST', headers: {'content-type': 'application/json'},
            body: JSON.stringify({sessionId: s.usageSessionId, callId: call.id, name: call.name, args: call.args}),
            signal: s.abort.signal,
          });
          result = await response.json();
          if (call.name === 'memoire_jarvis' && response.ok) refreshMemoryStatus();
          if (!response.ok) result = {error: result.error || 'Consultation indisponible.'};
          if(response.ok&&result?.clientAction&&active===s&&!s.cancelledTools.has(call.id)){
            const effect=result.clientAction;delete result.clientAction;
            result.browser=await window.jarvisCapabilities?.execute(effect,{space:s.space});
          }
        } catch { result = {error: 'Consultation Home Assistant indisponible.'}; }
        if (active === s && !s.cancelledTools.has(call.id))
          send(s, {toolResponse: {functionResponses: [{id: call.id, name: call.name, response: result}]}});
        })();
      }
    }
    const content = data.serverContent;
    if (content) {
      if (content.interrupted) {
        s.awaitingToolAnswer=false;monitor.interrupt('server');document.dispatchEvent(new CustomEvent('jarvis:voice-interrupt',{detail:{source:'server'}}));
        flushTranscript(s,'interrupted',true);
        clearPlayback(s);
        s.rows = {};
        s.lastSpeech = Date.now();
        paint('Je t’écoute.');
      }
      if (content.inputTranscription?.text) {
        s.lastSpeech = Date.now();
        transcript(s, 'user', content.inputTranscription.text);
      }
      if (content.outputTranscription?.text) {s.awaitingToolAnswer=false;transcript(s, 'model', content.outputTranscription.text);}
      for (const part of content.modelTurn?.parts || []) {
        if(part.inlineData&&!content.interrupted)play(s,part.inlineData);
      }
      if(content.generationComplete)monitor.generationComplete();
      if (content.generationComplete || content.turnComplete) s.playback.port.postMessage({type:'end'});
      if(content.turnComplete){s.serverTurnComplete=true;s.receivingModelTurn=false;monitor.turnComplete(!!s.awaitingToolAnswer);}
      if (content.turnComplete && !s.awaitingToolAnswer) {flushTranscript(s,'complete',true);s.rows = {};monitor.publish(true);}
    }
    if (data.goAway) stop('La session Google se termine. Réouvre le micro pour continuer.');
  }

  button.addEventListener('click', async () => {
    if (active) {toggleMute();return;}
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      paint('Ouvre la version HTTPS pour autoriser le micro.', true);
      httpsLink.hidden = false;
      return;
    }
    const s = {abort: new AbortController(), speaking: false, rows: {}, ready: false, usageSequence: 0, cancelledTools: new Set(),space:document.querySelector('#spaceSelect').value,archiveTurn:0,archiveRow:{user:'',assistant:'',revision:0}};
    active = s;monitor.connect();
    paint('Ouverture de la conversation…');
    document.querySelector('#liveTranscript').replaceChildren();
    try {
      // Resume on the user gesture, particularly for Safari on iPhone.
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      s.ctx = new AudioContext({latencyHint: 'interactive'});
      await s.ctx.resume();
      if (active !== s) return;
      s.timeout = setTimeout(() => {
        if (active === s) stop('La connexion vocale prend trop de temps. Réessaie.', true);
      }, 30000);
      const response = await fetch('/api/jarvis/live/session?space=' + encodeURIComponent(s.space), {
        method: 'POST', headers: {'content-type': 'application/json'},
        body: '{}', signal: s.abort.signal,
      });
      const session = await response.json();
      if (active !== s) return;
      if (!response.ok) throw Error(session.error || 'La voix est indisponible.');
      s.usageSessionId = session.usageSessionId;
      s.maxSeconds = Math.min(600, session.maxSeconds || 600);
      paint('Autorise le micro pour commencer.');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      });
      if (active !== s) { stream.getTracks().forEach(t => t.stop()); return; }
      s.stream = stream;for(const track of stream.getAudioTracks())track.enabled=!s.muted;
      stream.getAudioTracks()[0].onended = () => { if (active === s) stop('Le micro a été déconnecté.'); };
      paint('Connexion audio en cours…');
      await s.ctx.audioWorklet.addModule('live-pcm.js?v=20261112-mech1');
      if (active !== s) return;
      s.mic = s.ctx.createMediaStreamSource(stream);
      s.processor = new AudioWorkletNode(s.ctx, 'jarvis-pcm', {outputChannelCount: [1]});
      s.playback = new AudioWorkletNode(s.ctx, 'jarvis-playback', {numberOfInputs: 0, outputChannelCount: [1]});
      s.playback.port.onmessage = ({data}) => {
        if (active !== s) return;
        if((data.type==='meter'||data.type==='drained')&&data.epoch!==(s.playbackEpoch||0))return;
        if(data.type==='meter'){s.speaking=data.playing;monitor.playback(data);}
        if(data.type==='drained'){s.speaking=false;monitor.drained();}
        if (data.type === 'overflow') stop('Connexion audio instable. Réouvre le micro.', true);
      };
      s.playback.connect(s.ctx.destination);
      s.gate = new JarvisVoiceGate({
        // Local energy is not proof of a barge-in: speakers can leak into the
        // mic despite AEC. Keep forwarding speech, but only Gemini's explicit
        // interrupted event may discard its output. Never latch packet rejection
        // on local VAD; without a server acknowledgement that silenced the turn.
        start: () => {if(active!==s)return;const prior=monitor.snapshot();if(prior.playing||prior.waiting||prior.pendingAudio)document.dispatchEvent(new CustomEvent('jarvis:voice-interrupt',{detail:{source:'microphone'}}));s.turnAnswered=false;window.jarvisCancelAsk?.();monitor.speechStart();},
        audio: data => {
          if(active!==s||!s.ready)return;
          if(s.ws.bufferedAmount>128000){stop('Connexion trop lente pour la voix. Réessaie.',true);return;}
          const bytes=new Uint8Array(data);let binary='';
          for(let i=0;i<bytes.length;i++)binary+=String.fromCharCode(bytes[i]);
          send(s,{realtimeInput:{audio:{mimeType:'audio/pcm;rate=16000',data:btoa(binary)}}});
        },
        end: () => {send(s,{realtimeInput:{audioStreamEnd:true}});if(active===s&&!s.turnAnswered)monitor.wait('fin de parole locale');},
        activity: () => {if(active===s)s.lastSpeech=Date.now();},
      });
      s.processor.port.onmessage=({data})=>{if(active!==s||!s.ready||s.muted)return;s.gate.push(data);if(active!==s)return;const pcm=new Int16Array(data);let sum=0,square=0,peak=0;for(const sample of pcm){const value=sample/32768;sum+=value;square+=value*value;peak=Math.max(peak,Math.abs(value));}const length=Math.max(1,pcm.length);monitor.input(Math.sqrt(Math.max(0,square/length-(sum/length)**2)),peak,s.gate.active&&s.gate.quiet<120);};
      s.mic.connect(s.processor);
      s.processor.connect(s.ctx.destination);
      s.ws = new WebSocket(session.websocketUrl + '?access_token=' + encodeURIComponent(session.token));
      s.ws.onopen = () => { if (active === s) send(s, {setup: session.setup}); };
      // Preserve server message order, including binary Blob decoding.
      s.incoming = Promise.resolve();
      s.ws.onmessage = event => {
        s.incoming = s.incoming.then(() => receive(s, event)).catch(() => {
          if (active === s) stop('La session audio a été interrompue. Réouvre le micro.', true);
        });
      };
      s.ws.onerror = () => { if (active === s) stop('Connexion vocale Google impossible. Réessaie.', true); };
      s.ws.onclose = () => {
        if (active === s) stop(s.ready ? 'Conversation terminée. Tu peux réouvrir le micro.' :
          'Google refuse la session. Vérifie l’accès au modèle Gemini Live et le quota.', !s.ready);
      };
    } catch (e) {
      if (active !== s) return;
      const message = e.name === 'NotAllowedError' ? 'Autorise le micro dans les réglages de ton navigateur.' :
        e.name === 'NotFoundError' ? 'Aucun micro trouvé sur cet appareil.' :
        e.name === 'NotReadableError' ? 'Le micro est occupé ou inaccessible.' :
        e.message || 'Impossible d’ouvrir la conversation vocale.';
      stop(message, true);
    }
  });

  document.addEventListener('jarvis:spacechange', () => { if (active) stop('Micro coupé au changement de personne.'); });
  document.addEventListener('jarvis:newconversation', () => stop('Nouvelle conversation. Touche J.A.R.V.I.S. pour ouvrir le micro.'));
  document.addEventListener('jarvis:writtenask', () => { if (active) stop('Micro coupé pour passer à l’écrit.'); });
  window.addEventListener('pagehide', () => stop());
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && active) stop('Micro coupé lorsque tu quittes la page.');
  });
  if (!window.isSecureContext) {
    const url = new URL(location.href);
    url.protocol = 'https:';
    url.port = '8788';
    httpsLink.href = url.href;
    httpsLink.hidden = false;
    paint('Le micro nécessite la version HTTPS.');
  }
})();
