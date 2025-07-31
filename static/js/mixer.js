document.addEventListener('DOMContentLoaded', () => {
    console.log('Mixer.js loaded, initializing controls');
    if (typeof io === 'undefined') {
        console.error('Socket.IO library not loaded');
        return;
    }
    if (typeof Nexus === 'undefined') {
        console.error('NexusUI library not loaded - creating fallback controls');
        initializeFallbackControls();
        return;
    }

    const socketUrl = `${window.location.protocol}//${window.location.host}`;
    const socket = io(socketUrl, { 
        transports: ['websocket', 'polling'],
        timeout: 5000,
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
    });

    socket.on('connect', () => {
        console.log('WebSocket connected to', socketUrl);
        socket.emit('streamConfig', { request: 'current_config' });
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection failed:', error);
        initializeOfflineMode();
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    initializeNexusControls(socket);

    socket.emit('streamConfig', { request: 'current_config' });
    socket.on('configUpdate', data => {
        console.log('Configuration updated:', data.streams);
    });

    function animate() {
        requestAnimationFrame(animate);
    }
    animate();
});

function initializeNexusControls(socket) {
    const controls = new Map();

    document.querySelectorAll('.stream-panel').forEach(panel => {
        const streamId = panel.dataset.streamId;
        panel.querySelectorAll('.audio-control').forEach(control => {
            const faderElement = control.querySelector('.fader');
            const muteElement = control.querySelector('.mute-toggle');
            const canvasElement = control.querySelector('.vu-meter');

            if (!faderElement || !muteElement || !canvasElement) {
                console.warn(`Missing control elements for stream ${streamId}`);
                return;
            }

            const sourceId = faderElement.id.split('-').slice(2).join('-'); // Handle sanitized IDs
            const controlKey = `${streamId}-${sourceId}`;

            try {
                const fader = new Nexus.Slider(`#fader-${streamId}-${sourceId}`, {
                    size: [60, 200],
                    min: 0,
                    max: 100,
                    value: 50
                });

                const mute = new Nexus.Toggle(`#mute-${streamId}-${sourceId}`, {
                    size: [40, 40],
                    state: false
                });

                const canvas = document.getElementById(`vu-${streamId}-${sourceId}`);
                const ctx = canvas.getContext('2d');

                controls.set(controlKey, { fader, mute, canvas, ctx });

                fader.on('change', value => {
                    console.log(`Sending volume for ${streamId}/${sourceId}: ${value}`);
                    if (socket.connected) {
                        socket.emit('audioControl', { streamId, sourceId, property: 'volume', value });
                    }
                });

                mute.on('change', value => {
                    console.log(`Sending mute for ${streamId}/${sourceId}: ${value}`);
                    if (socket.connected) {
                        socket.emit('audioControl', { streamId, sourceId, property: 'mute', value });
                    }
                });

                socket.on('audioLevels', data => {
                    if (data.streamId === streamId && data.sourceId === sourceId) {
                        updateVUMeter(ctx, canvas, data.level);
                    }
                });

                console.log(`Controls initialized for ${streamId}/${sourceId}`);
            } catch (error) {
                console.error(`Error initializing controls for ${streamId}/${sourceId}:`, error);
            }
        });
    });
}

function updateVUMeter(ctx, canvas, level) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const segments = 20;
    const normalizedLevel = Math.max(0, Math.min(1, level / 100));

    for (let i = 0; i < segments; i++) {
        const segmentHeight = canvas.height / segments;
        const y = canvas.height - (i + 1) * segmentHeight;
        let color;
        if (i / segments < 0.7) {
            color = '#00d4ff';
        } else if (i / segments < 0.9) {
            color = '#ffaa00';
        } else {
            color = '#ff0000';
        }
        ctx.fillStyle = i / segments < normalizedLevel ? color : '#1a1a1a';
        ctx.fillRect(0, y, canvas.width, segmentHeight - 1);
    }
}

function initializeFallbackControls() {
    console.log('Initializing fallback HTML controls');
    document.querySelectorAll('.stream-panel').forEach(panel => {
        const streamId = panel.dataset.streamId;
        panel.querySelectorAll('.audio-control').forEach(control => {
            const faderElement = control.querySelector('.fader');
            const muteElement = control.querySelector('.mute-toggle');
            if (faderElement && muteElement) {
                const sourceId = faderElement.id.split('-').slice(2).join('-');
                faderElement.innerHTML = `
                    <input type="range" 
                           min="0" 
                           max="100" 
                           value="50" 
                           class="fallback-fader"
                           data-stream="${streamId}"
                           data-source="${sourceId}">
                    <span class="volume-value">50</span>
                `;
                muteElement.innerHTML = `
                    <button class="fallback-mute"
                            data-stream="${streamId}"
                            data-source="${sourceId}">
                        Mute
                    </button>
                `;
                const slider = faderElement.querySelector('.fallback-fader');
                const valueSpan = faderElement.querySelector('.volume-value');
                const muteBtn = muteElement.querySelector('.fallback-mute');
                slider.addEventListener('input', (e) => {
                    const value = e.target.value;
                    valueSpan.textContent = value;
                    console.log(`Fallback volume for ${streamId}/${sourceId}: ${value}`);
                });
                muteBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const isMuted = muteBtn.classList.toggle('muted');
                    muteBtn.textContent = isMuted ? 'Unmute' : 'Mute';
                    console.log(`Fallback mute for ${streamId}/${sourceId}: ${isMuted}`);
                });
            }
        });
    });
}

function initializeOfflineMode() {
    console.log('Running in offline mode - WebSocket unavailable');
    const indicator = document.createElement('div');
    indicator.id = 'offline-indicator';
    indicator.textContent = '⚠️ Offline Mode - Controls are local only';
    document.body.appendChild(indicator);
}