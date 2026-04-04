// ========== 国风音效系统 ==========
class ChineseSoundFX {
    constructor() {
        this.audioCtx = null;
        this.enabled = true;
        this.masterVolume = 0.5;
        this.initialized = false;
        this.autoInit = true;
        this.bgmEnabled = false;
        this.bgmPlaying = false;
        this.bgmGain = null;
        this.bgmInterval = null;
        this.bgmAudio = null;
    }

    init() {
        if (this.initialized) return;
        try {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.initialized = true;
        } catch (e) {
            console.warn('Web Audio API not supported');
            this.enabled = false;
        }
    }

    ensureInit() {
        if (!this.initialized && this.autoInit) {
            this.init();
        }
    }

    resume() {
        if (!this.audioCtx) {
            this.init();
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    }

    createOscillator(type, freq, duration, gainValue = 0.3) {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(freq * 3, this.audioCtx.currentTime);
        gain.gain.setValueAtTime(gainValue * this.masterVolume, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc.stop(this.audioCtx.currentTime + duration);
        
        return { osc, gain, filter };
    }

    playDiceRoll() {
        if (!this.enabled) return;
        this.ensureInit();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        for (let i = 0; i < 3; i++) {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            const filter = this.audioCtx.createBiquadFilter();
            
            osc.type = 'square';
            osc.frequency.setValueAtTime(200 + Math.random() * 100, now + i * 0.05);
            osc.frequency.exponentialRampToValueAtTime(100, now + i * 0.05 + 0.1);
            
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(300, now + i * 0.05);
            filter.Q.setValueAtTime(5, now + i * 0.05);
            
            gain.gain.setValueAtTime(0.1 * this.masterVolume, now + i * 0.05);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.05 + 0.1);
            
            osc.connect(filter);
            filter.connect(gain);
            gain.connect(this.audioCtx.destination);
            
            osc.start(now + i * 0.05);
            osc.stop(now + i * 0.05 + 0.1);
        }
    }

    playTurnAnnouncement() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        
        for (let i = 0; i < 2; i++) {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(80, now + i * 0.3);
            osc.frequency.exponentialRampToValueAtTime(40, now + i * 0.3 + 0.3);
            
            gain.gain.setValueAtTime(0.4 * this.masterVolume, now + i * 0.3);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.3 + 0.4);
            
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            
            osc.start(now + i * 0.3);
            osc.stop(now + i * 0.3 + 0.4);
        }
    }

    playPieceMove() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(150, now);
        osc.frequency.exponentialRampToValueAtTime(80, now + 0.15);
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(400, now);
        filter.frequency.exponentialRampToValueAtTime(100, now + 0.15);
        
        gain.gain.setValueAtTime(0.15 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc.stop(now + 0.2);
    }

    playCombatStart() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        
        const osc1 = this.audioCtx.createOscillator();
        const osc2 = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc1.type = 'sawtooth';
        osc1.frequency.setValueAtTime(800, now);
        osc1.frequency.exponentialRampToValueAtTime(400, now + 0.2);
        
        osc2.type = 'sawtooth';
        osc2.frequency.setValueAtTime(1200, now);
        osc2.frequency.exponentialRampToValueAtTime(600, now + 0.15);
        
        filter.type = 'highpass';
        filter.frequency.setValueAtTime(500, now);
        
        gain.gain.setValueAtTime(0.2 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        
        osc1.connect(filter);
        osc2.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc1.start();
        osc2.start();
        osc1.stop(now + 0.3);
        osc2.stop(now + 0.3);
    }

    playVictory() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        
        const osc = this.audioCtx.createOscillator();
        const osc2 = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(400, now);
        
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(600, now + 0.1);
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(2000, now);
        
        gain.gain.setValueAtTime(0.4 * this.masterVolume, now);
        gain.gain.setValueAtTime(0.5 * this.masterVolume, now + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1.5);
        
        osc.connect(filter);
        osc2.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc2.start(now + 0.1);
        osc.stop(now + 1.5);
        osc2.stop(now + 1.5);
    }

    playDefeat() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(200, now);
        osc.frequency.exponentialRampToValueAtTime(100, now + 2);
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(500, now);
        
        gain.gain.setValueAtTime(0.3 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 2.5);
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc.stop(now + 2.5);
    }

    playTurnEnd() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();

        const now = this.audioCtx.currentTime;

        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(523, now);
        osc.frequency.setValueAtTime(659, now + 0.3);

        gain.gain.setValueAtTime(0.4 * this.masterVolume, now);
        gain.gain.setValueAtTime(0.5 * this.masterVolume, now + 0.3);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1);

        osc.connect(gain);
        gain.connect(this.audioCtx.destination);

        osc.start();
        osc.stop(now + 1);
    }

    playAIThinking() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        const filter = this.audioCtx.createBiquadFilter();
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(220, now);
        
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(300, now);
        
        gain.gain.setValueAtTime(0.05 * this.masterVolume, now);
        gain.gain.linearRampToValueAtTime(0.08 * this.masterVolume, now + 0.5);
        gain.gain.linearRampToValueAtTime(0.05 * this.masterVolume, now + 1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc.stop(now + 1.2);
    }

    playClick() {
        if (!this.enabled) return;
        this.ensureInit();
        if (!this.audioCtx) return;
        this.resume();

        const now = this.audioCtx.currentTime;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.exponentialRampToValueAtTime(600, now + 0.05);

        gain.gain.setValueAtTime(0.7 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

        osc.connect(gain);
        gain.connect(this.audioCtx.destination);

        osc.start();
        osc.stop(now + 0.1);
    }

    playCardGain() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        
        for (let i = 0; i < 3; i++) {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(523 * Math.pow(1.26, i), now + i * 0.15);
            
            gain.gain.setValueAtTime(0, now);
            gain.gain.setValueAtTime(0.15 * this.masterVolume, now + i * 0.15);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.15 + 0.3);
            
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            
            osc.start(now + i * 0.15);
            osc.stop(now + i * 0.15 + 0.3);
        }
    }

    playCheck() {
        if (!this.enabled) return;
        this.init();
        if (!this.audioCtx) return;
        this.resume();
        
        const now = this.audioCtx.currentTime;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        
        osc.type = 'square';
        osc.frequency.setValueAtTime(300, now);
        osc.frequency.setValueAtTime(400, now + 0.1);
        
        gain.gain.setValueAtTime(0.15 * this.masterVolume, now);
        gain.gain.setValueAtTime(0.2 * this.masterVolume, now + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        
        osc.start();
        osc.stop(now + 0.4);
    }

    startBGM() {
        if (!this.enabled) return;
        if (this.bgmPlaying) return;
        
        this.bgmEnabled = true;
        
        this.bgmAudio = new Audio('/static/bgm.mp3');
        this.bgmAudio.loop = true;
        this.bgmAudio.volume = 0.15;
        
        this.bgmAudio.play().then(() => {
            this.bgmPlaying = true;
        }).catch(err => {
            console.warn('BGM playback failed:', err);
        });
    }

    stopBGM() {
        this.bgmEnabled = false;
        this.bgmPlaying = false;
        
        if (this.bgmAudio) {
            this.bgmAudio.pause();
            this.bgmAudio.currentTime = 0;
            this.bgmAudio = null;
        }
    }
}

const soundFX = new ChineseSoundFX();

document.addEventListener('click', () => {
    soundFX.init();
    if (soundFX.enabled && !soundFX.bgmPlaying) {
        soundFX.startBGM();
    }
}, { once: true });
document.addEventListener('keydown', () => {
    soundFX.init();
    if (soundFX.enabled && !soundFX.bgmPlaying) {
        soundFX.startBGM();
    }
}, { once: true });

function toggleSound() {
    soundFX.init();
    soundFX.enabled = !soundFX.enabled;
    const btn = document.getElementById('btn-toggle-sound');
    
    if (soundFX.enabled) {
        if (!soundFX.bgmPlaying) {
            soundFX.startBGM();
        }
        if (btn) {
            btn.innerText = '🔊';
            btn.classList.add('btn-sound-on');
            btn.classList.remove('btn-sound-off');
        }
    } else {
        soundFX.stopBGM();
        if (btn) {
            btn.innerText = '🔇';
            btn.classList.add('btn-sound-off');
            btn.classList.remove('btn-sound-on');
        }
    }
}
