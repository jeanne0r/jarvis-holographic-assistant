// Average and resample microphone frames to mono PCM16 / 16 kHz, in 20 ms packets.
class JarvisPCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.weight = 0;
    this.sum = 0;
    this.packet = new Int16Array(320);
    this.index = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const sample of input) {
      let remaining = 1;
      while (remaining > 1e-8) {
        const take = Math.min(remaining, this.ratio - this.weight);
        this.sum += sample * take;
        this.weight += take;
        remaining -= take;
        if (this.weight >= this.ratio - 1e-8) {
          const value = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.packet[this.index++] = Math.round(value * (value < 0 ? 32768 : 32767));
          this.sum = this.weight = 0;
          if (this.index === this.packet.length) {
            this.port.postMessage(this.packet.buffer, [this.packet.buffer]);
            this.packet = new Int16Array(320);
            this.index = 0;
          }
        }
      }
    }
    // Outputs remain silent: microphone audio must never play through the speakers.
    return true;
  }
}
registerProcessor('jarvis-pcm', JarvisPCM);

// Play one continuous PCM stream on the audio thread. Packet boundaries must
// never become playback boundaries or restart the sample-rate conversion.
class JarvisPlayback extends AudioWorkletProcessor {
  constructor() {
    super();
    this.inputRate = 24000;
    this.ring = new Float32Array(this.inputRate * 30);
    this.head = this.count = this.fraction = 0;
    this.playing = false;
    this.ended = false;
    this.ramp = this.last = this.tailValue = this.fadeLeft = 0;
    this.fadeFrames = Math.max(1, Math.round(sampleRate * 0.004));
    this.drained = true;
    this.epoch=0;this.meterSamples=0;this.meterSquare=0;this.meterPeak=0;this.meterPlaying=false;
    this.port.onmessage = ({data}) => {
      if (data.type === 'clear') { this.epoch=Number.isSafeInteger(data.epoch)?data.epoch:this.epoch+1;this.clear();this.meterSamples=this.meterSquare=this.meterPeak=0;this.meterPlaying=false;this.port.postMessage({type:'meter',epoch:this.epoch,rms:0,peak:0,playing:false,bufferedMs:0});return; }
      if (data.type === 'end') { this.ended = true; this.drained = false; return; }
      if (data.type !== 'audio' || !(data.samples instanceof Float32Array)) return;
      const rate = data.rate;
      if (!Number.isFinite(rate) || rate < 8000 || rate > 96000) return;
      if (rate !== this.inputRate) {
        this.clear();
        this.inputRate = rate;
        this.ring = new Float32Array(rate * 30);
      }
      if (this.count + data.samples.length > this.ring.length) {
        this.port.postMessage({type: 'overflow'});
        this.clear();
        return;
      }
      let tail = (this.head + this.count) % this.ring.length;
      for (const value of data.samples) {
        this.ring[tail] = Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0;
        tail = (tail + 1) % this.ring.length;
      }
      this.count += data.samples.length;
      this.ended = false;
      this.drained = false;
    };
  }
  fadeOut() {
    this.tailValue = this.last;
    this.fadeLeft = this.fadeFrames;
    this.playing = false;
    this.ramp = 0;
  }
  clear() {
    // Discard all queued speech at once; only a 4 ms fade prevents a click.
    this.fadeOut();
    this.head = this.count = this.fraction = 0;
    this.ended = false;
  }
  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) return true;
    const step = this.inputRate / sampleRate;
    const target = Math.ceil(this.inputRate * 0.18);
    for (let i = 0; i < output.length; i++) {
      if (!this.playing && (this.count >= target || (this.ended && this.count > 0))) {
        this.playing = true;
        this.ramp = 0;
      }
      let value = 0;
      if (this.playing) {
        if (this.count >= 2 || (this.ended && this.count === 1)) {
          const a = this.ring[this.head];
          const b = this.count > 1 ? this.ring[(this.head + 1) % this.ring.length] : a;
          this.ramp = Math.min(1, this.ramp + 1 / this.fadeFrames);
          value = (a + (b - a) * this.fraction) * this.ramp;
          this.fraction += step;
          const consumed = Math.min(this.count, Math.floor(this.fraction));
          this.head = (this.head + consumed) % this.ring.length;
          this.count -= consumed;
          this.fraction -= consumed;
          if (!this.count) this.fraction = 0;
        } else {
          this.fadeOut();
        }
      }
      if (this.fadeLeft > 0) value += this.tailValue * (--this.fadeLeft / this.fadeFrames);
      output[i] = Math.max(-1, Math.min(1, value));
      this.last = output[i];
      this.meterSquare+=output[i]*output[i];this.meterPeak=Math.max(this.meterPeak,Math.abs(output[i]));this.meterSamples++;
    }
    const audible=this.playing||this.fadeLeft>0;
    if(this.meterSamples>=sampleRate*.04||audible!==this.meterPlaying){this.port.postMessage({type:'meter',epoch:this.epoch,rms:Math.sqrt(this.meterSquare/Math.max(1,this.meterSamples)),peak:this.meterPeak,playing:audible,bufferedMs:this.count/this.inputRate*1000});this.meterSamples=this.meterSquare=this.meterPeak=0;this.meterPlaying=audible;}
    if (!this.count && !this.playing && !this.fadeLeft && !this.drained) {
      this.drained = true;
      this.port.postMessage({type: 'drained',epoch:this.epoch,ended:this.ended});
    }
    return true;
  }
}
registerProcessor('jarvis-playback', JarvisPlayback);
