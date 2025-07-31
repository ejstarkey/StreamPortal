// Bowling Broadcast Camera Control JavaScript

class BowlingCameraController {
    constructor() {
        this.selectedCamera = null;
        this.selectedCameras = new Set();
        this.ptzSpeed = 32;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCameraStatuses();
        this.updateSensitivityDisplay();
        this.updateSpeedDisplay();
    }

    setupEventListeners() {
        // Camera discovery
        const discoverBtn = document.getElementById('discover-cameras-btn');
        if (discoverBtn) {
            discoverBtn.addEventListener('click', () => this.discoverCameras());
        }

        const importBtn = document.getElementById('import-cameras-btn');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.importDiscoveredCameras());
        }

        // Camera selection
        const cameraSelect = document.getElementById('selected-camera');
        if (cameraSelect) {
            cameraSelect.addEventListener('change', (e) => {
                this.selectedCamera = e.target.value;
                this.updateControlsState();
            });
        }

        // Quick select buttons
        document.querySelectorAll('.quick-select').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const cameraId = e.target.dataset.cameraId;
                this.selectCamera(cameraId);
            });
        });

        // Quick snapshot buttons
        document.querySelectorAll('.quick-snapshot').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const cameraId = e.target.dataset.cameraId;
                this.takeQuickSnapshot(cameraId);
            });
        });

        // Quick preset buttons
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const preset = e.target.dataset.preset;
                this.executeQuickPreset(preset);
            });
        });

        // PTZ Controls
        document.querySelectorAll('.ptz-btn[data-operation]').forEach(btn => {
            btn.addEventListener('mousedown', (e) => this.startPTZ(e.target.dataset.operation));
            btn.addEventListener('mouseup', () => this.stopPTZ());
            btn.addEventListener('mouseleave', () => this.stopPTZ());
            btn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                this.startPTZ(e.target.dataset.operation);
            });
            btn.addEventListener('touchend', (e) => {
                e.preventDefault();
                this.stopPTZ();
            });
        });

        // PTZ Speed
        const speedSlider = document.getElementById('ptz-speed');
        if (speedSlider) {
            speedSlider.addEventListener('input', () => this.updateSpeedDisplay());
        }

        // Manual presets
        const setPresetBtn = document.getElementById('set-preset-btn');
        if (setPresetBtn) {
            setPresetBtn.addEventListener('click', () => this.setPreset());
        }

        const gotoPresetBtn = document.getElementById('goto-preset-btn');
        if (gotoPresetBtn) {
            gotoPresetBtn.addEventListener('click', () => this.gotoPreset());
        }

        // Broadcast mode buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.target.dataset.mode;
                this.setBroadcastMode(mode);
            });
        });

        // Spotlight control
        const spotlightToggle = document.getElementById('spotlight-toggle');
        if (spotlightToggle) {
            spotlightToggle.addEventListener('click', () => this.toggleSpotlight());
        }

        // Detection settings
        const saveDetectionBtn = document.getElementById('save-detection-btn');
        if (saveDetectionBtn) {
            saveDetectionBtn.addEventListener('click', () => this.saveDetectionSettings());
        }

        const sensitivitySlider = document.getElementById('sensitivity-slider');
        if (sensitivitySlider) {
            sensitivitySlider.addEventListener('input', () => this.updateSensitivityDisplay());
        }

        // Snapshot button
        const snapshotBtn = document.getElementById('take-snapshot-btn');
        if (snapshotBtn) {
            snapshotBtn.addEventListener('click', () => this.takeSnapshot());
        }

        // Bulk operations
        document.querySelectorAll('[data-type]').forEach(btn => {
            if (btn.classList.contains('btn-secondary')) {
                btn.addEventListener('click', (e) => {
                    const type = e.target.dataset.type;
                    this.selectCamerasByType(type);
                });
            }
        });

        const bulkPresetBtn = document.getElementById('bulk-preset-btn');
        if (bulkPresetBtn) {
            bulkPresetBtn.addEventListener('click', () => this.bulkPresetAction());
        }

        const bulkSpotlightBtn = document.getElementById('bulk-spotlight-btn');
        if (bulkSpotlightBtn) {
            bulkSpotlightBtn.addEventListener('click', () => this.bulkSpotlightAction());
        }

        const bulkTestBtn = document.getElementById('bulk-test-btn');
        if (bulkTestBtn) {
            bulkTestBtn.addEventListener('click', () => this.bulkTestCameras());
        }

        // Manual camera addition
        const addManualBtn = document.getElementById('add-manual-camera-btn');
        if (addManualBtn) {
            addManualBtn.addEventListener('click', () => this.openManualCameraModal());
        }

        // Modal controls
        this.setupModalEventListeners();
    }

    setupModalEventListeners() {
        // Import modal
        const closeImportModal = document.getElementById('close-import-modal');
        if (closeImportModal) {
            closeImportModal.addEventListener('click', () => this.closeImportModal());
        }

        // Manual camera modal
        const closeManualModal = document.getElementById('close-manual-modal');
        if (closeManualModal) {
            closeManualModal.addEventListener('click', () => this.closeManualCameraModal());
        }

        const cancelManualBtn = document.getElementById('cancel-manual-camera');
        if (cancelManualBtn) {
            cancelManualBtn.addEventListener('click', () => this.closeManualCameraModal());
        }

        const manualForm = document.getElementById('manual-camera-form');
        if (manualForm) {
            manualForm.addEventListener('submit', (e) => this.addManualCamera(e));
        }

        // Close modals when clicking outside
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });
    }

    // Camera Discovery Methods
    async discoverCameras() {
        const button = document.getElementById('discover-cameras-btn');
        button.disabled = true;
        button.textContent = 'Discovering...';

        try {
            const response = await fetch('/camera/api/camera/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();
            if (result.success) {
                this.displayDiscoveredCameras(result.discovered_cameras);
                this.showMessage(`Discovered ${result.count} cameras from streams configuration`, 'success');
            } else {
                this.showMessage(`Discovery failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Discovery error: ${error.message}`, 'error');
        } finally {
            button.disabled = false;
            button.textContent = 'Discover Cameras from Streams';
        }
    }

    displayDiscoveredCameras(cameras) {
        const resultsDiv = document.getElementById('discovery-results');
        const listDiv = document.getElementById('discovered-cameras-list');
        
        if (Object.keys(cameras).length === 0) {
            listDiv.innerHTML = '<p>No cameras found in streams configuration. Make sure you have RTSP cameras configured in your lane pairs.</p>';
            resultsDiv.style.display = 'block';
            return;
        }

        let html = '<h4>Discovered Cameras:</h4>';
        for (const [cameraId, camera] of Object.entries(cameras)) {
            html += `
                <div class="discovered-camera">
                    <label class="checkbox-label">
                        <input type="checkbox" data-camera-id="${cameraId}" checked>
                        <strong>${camera.name}</strong> - ${camera.ip}
                    </label>
                    <div class="camera-details">
                        <p>Type: ${camera.type} | Lane: ${camera.lane_pair}</p>
                        <div class="credential-inputs">
                            <input type="text" placeholder="Username" value="${camera.username}" data-field="username" data-camera-id="${cameraId}">
                            <input type="password" placeholder="Password" data-field="password" data-camera-id="${cameraId}">
                            <input type="number" placeholder="Port" value="${camera.port}" data-field="port" data-camera-id="${cameraId}">
                        </div>
                    </div>
                </div>
            `;
        }
        
        listDiv.innerHTML = html;
        resultsDiv.style.display = 'block';
    }

    async importDiscoveredCameras() {
        const checkboxes = document.querySelectorAll('#discovered-cameras-list input[type="checkbox"]');
        const camerasToImport = {};

        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                const cameraId = checkbox.dataset.cameraId;
                const container = checkbox.closest('.discovered-camera');
                
                camerasToImport[cameraId] = {
                    import: true,
                    username: container.querySelector('[data-field="username"]').value,
                    password: container.querySelector('[data-field="password"]').value,
                    port: parseInt(container.querySelector('[data-field="port"]').value) || 80
                };
            }
        });

        if (Object.keys(camerasToImport).length === 0) {
            this.showMessage('No cameras selected for import', 'warning');
            return;
        }

        try {
            const response = await fetch('/camera/api/camera/import_discovered', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cameras: camerasToImport })
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Successfully imported ${result.imported_count} cameras`, 'success');
                this.closeImportModal();
                setTimeout(() => window.location.reload(), 1000);
            } else {
                this.showMessage(`Import failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Import error: ${error.message}`, 'error');
        }
    }

    // Camera Control Methods
    selectCamera(cameraId) {
        this.selectedCamera = cameraId;
        const select = document.getElementById('selected-camera');
        if (select) {
            select.value = cameraId;
        }
        this.updateControlsState();
        this.showMessage(`Selected ${this.getCameraName(cameraId)}`, 'info');
    }

    async executeQuickPreset(presetName) {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/ptz`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'quick_preset',
                    preset_name: presetName
                })
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Camera moved to ${presetName} position`, 'success');
            } else {
                this.showMessage(`Failed to execute preset: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Preset error: ${error.message}`, 'error');
        }
    }

    async setBroadcastMode(mode) {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/broadcast_mode`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode })
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Camera set to ${mode} broadcast mode`, 'success');
                // Update UI to show active mode
                document.querySelectorAll('.mode-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.mode === mode);
                });
            } else {
                this.showMessage(`Failed to set broadcast mode: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Broadcast mode error: ${error.message}`, 'error');
        }
    }

    // PTZ Control Methods
    updateSpeedDisplay() {
        const slider = document.getElementById('ptz-speed');
        const valueDisplay = document.getElementById('speed-value');
        if (slider && valueDisplay) {
            this.ptzSpeed = parseInt(slider.value);
            valueDisplay.textContent = this.ptzSpeed;
        }
    }

    startPTZ(operation) {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }
        this.sendPTZCommand(operation);
    }

    stopPTZ() {
        if (!this.selectedCamera) return;
        this.sendPTZCommand('stop');
    }

    async sendPTZCommand(operation) {
        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/ptz`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: operation,
                    speed: this.ptzSpeed
                })
            });

            const result = await response.json();
            if (!result.success && operation !== 'stop') {
                this.showMessage(`PTZ command failed: ${result.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            if (operation !== 'stop') {
                this.showMessage(`PTZ control error: ${error.message}`, 'error');
            }
        }
    }

    // Bulk Operations
    selectCamerasByType(type) {
        this.selectedCameras.clear();
        const cameraCards = document.querySelectorAll('.camera-card');
        
        cameraCards.forEach(card => {
            const cameraId = card.dataset.cameraId;
            const select = document.getElementById('selected-camera');
            const option = select ? select.querySelector(`option[value="${cameraId}"]`) : null;
            
            if (type === 'all') {
                this.selectedCameras.add(cameraId);
                card.classList.add('selected');
            } else if (option && option.dataset.type === type) {
                this.selectedCameras.add(cameraId);
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });

        this.showMessage(`Selected ${this.selectedCameras.size} cameras of type: ${type}`, 'info');
    }

    async bulkPresetAction() {
        if (this.selectedCameras.size === 0) {
            this.showMessage('No cameras selected for bulk operation', 'error');
            return;
        }

        const presetSelect = document.getElementById('bulk-preset-select');
        const presetId = parseInt(presetSelect.value);

        try {
            const response = await fetch('/camera/api/cameras/bulk_action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    camera_ids: Array.from(this.selectedCameras),
                    action: 'goto_preset',
                    params: { preset_id: presetId }
                })
            });

            const result = await response.json();
            if (result.success) {
                const successful = Object.values(result.results).filter(r => r.success).length;
                this.showMessage(`Bulk preset completed: ${successful}/${this.selectedCameras.size} cameras`, 'success');
            } else {
                this.showMessage(`Bulk preset failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Bulk operation error: ${error.message}`, 'error');
        }
    }

    async bulkTestCameras() {
        if (this.selectedCameras.size === 0) {
            this.showMessage('No cameras selected for testing', 'error');
            return;
        }

        try {
            const response = await fetch('/camera/api/cameras/bulk_action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    camera_ids: Array.from(this.selectedCameras),
                    action: 'take_snapshot',
                    params: {}
                })
            });

            const result = await response.json();
            if (result.success) {
                const successful = Object.values(result.results).filter(r => r.success).length;
                this.showMessage(`Camera test completed: ${successful}/${this.selectedCameras.size} cameras responding`, 'success');
                
                // Update status indicators
                for (const [cameraId, result] of Object.entries(result.results)) {
                    this.updateCameraStatus(cameraId, result.success ? 'online' : 'offline');
                }
            } else {
                this.showMessage(`Bulk test failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Bulk test error: ${error.message}`, 'error');
        }
    }

    // Utility Methods
    updateControlsState() {
        const controlsDisabled = !this.selectedCamera;
        
        // Disable/enable control buttons
        document.querySelectorAll('.ptz-btn, .preset-btn, .mode-btn, #take-snapshot-btn, #spotlight-toggle').forEach(btn => {
            btn.disabled = controlsDisabled;
            btn.style.opacity = controlsDisabled ? '0.5' : '1';
        });

        this.updateCameraPreview();
    }

    updateCameraPreview() {
        const previewDiv = document.getElementById('camera-preview');
        if (!previewDiv) return;

        if (this.selectedCamera) {
            const cameraName = this.getCameraName(this.selectedCamera);
            previewDiv.innerHTML = `
                <div class="camera-preview-info">
                    <h3>${cameraName}</h3>
                    <p>Live RTSP preview not implemented</p>
                    <p>Use OBS or external viewer for live preview</p>
                </div>
            `;
        } else {
            previewDiv.innerHTML = '<p>Select a camera to view preview</p>';
        }
    }

    getCameraName(cameraId) {
        const select = document.getElementById('selected-camera');
        const option = select ? select.querySelector(`option[value="${cameraId}"]`) : null;
        return option ? option.textContent : cameraId;
    }

    updateSensitivityDisplay() {
        const slider = document.getElementById('sensitivity-slider');
        const valueDisplay = document.getElementById('sensitivity-value');
        if (slider && valueDisplay) {
            valueDisplay.textContent = slider.value;
        }
    }

    // Existing methods from original implementation
    async setPreset() {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        const presetNumber = document.getElementById('preset-number').value;
        if (!presetNumber || presetNumber < 1 || presetNumber > 8) {
            this.showMessage('Please enter a valid preset number (1-8)', 'error');
            return;
        }

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/ptz`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'set_preset',
                    preset_id: parseInt(presetNumber)
                })
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Preset ${presetNumber} set successfully`, 'success');
            } else {
                this.showMessage(`Failed to set preset: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Preset error: ${error.message}`, 'error');
        }
    }

    async gotoPreset() {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        const presetNumber = document.getElementById('preset-number').value;
        if (!presetNumber || presetNumber < 1 || presetNumber > 8) {
            this.showMessage('Please enter a valid preset number (1-8)', 'error');
            return;
        }

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/ptz`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'goto_preset',
                    preset_id: parseInt(presetNumber)
                })
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Moved to preset ${presetNumber}`, 'success');
            } else {
                this.showMessage(`Failed to go to preset: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Preset error: ${error.message}`, 'error');
        }
    }

    async toggleSpotlight() {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        const button = document.getElementById('spotlight-toggle');
        const currentState = button.dataset.state === 'on';
        const newState = !currentState;

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/spotlight`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: newState })
            });

            const result = await response.json();
            if (result.success) {
                button.dataset.state = newState ? 'on' : 'off';
                button.querySelector('.state').textContent = newState ? 'ON' : 'OFF';
                button.classList.toggle('active', newState);
                this.showMessage(`Spotlight ${newState ? 'enabled' : 'disabled'}`, 'success');
            } else {
                this.showMessage(`Failed to control spotlight: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Spotlight control error: ${error.message}`, 'error');
        }
    }

    async saveDetectionSettings() {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        const settings = {
            motion_enabled: document.getElementById('motion-detection').checked,
            person_detection: document.getElementById('person-detection').checked,
            vehicle_detection: false, // Not needed for bowling
            sensitivity: parseInt(document.getElementById('sensitivity-slider').value)
        };

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/detection`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage('Detection settings saved for bowling broadcast', 'success');
            } else {
                this.showMessage(`Failed to save detection settings: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Detection settings error: ${error.message}`, 'error');
        }
    }

    async takeSnapshot() {
        if (!this.selectedCamera) {
            this.showMessage('Please select a camera first', 'error');
            return;
        }

        const button = document.getElementById('take-snapshot-btn');
        button.disabled = true;
        button.textContent = '📸 Capturing...';

        try {
            const response = await fetch(`/camera/api/camera/${this.selectedCamera}/snapshot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Snapshot captured: ${result.camera_type} - ${result.lane_pair}`, 'success');
                this.addSnapshotToGallery(result);
            } else {
                this.showMessage(`Failed to take snapshot: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Snapshot error: ${error.message}`, 'error');
        } finally {
            button.disabled = false;
            button.textContent = '📸 Take Snapshot';
        }
    }

    async takeQuickSnapshot(cameraId) {
        try {
            const response = await fetch(`/camera/api/camera/${cameraId}/snapshot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Quick snapshot: ${result.camera_type}`, 'success');
                this.addSnapshotToGallery(result);
            } else {
                this.showMessage(`Quick snapshot failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Quick snapshot error: ${error.message}`, 'error');
        }
    }

    addSnapshotToGallery(snapshot) {
        const gallery = document.getElementById('snapshot-grid');
        if (!gallery) return;

        const snapshotDiv = document.createElement('div');
        snapshotDiv.className = 'snapshot-item';
        snapshotDiv.innerHTML = `
            <img src="${snapshot.url}" alt="Snapshot" onclick="window.open('${snapshot.url}', '_blank')">
            <div class="snapshot-info">
                <div class="camera-type">${snapshot.camera_type}</div>
                <div class="lane-info">${snapshot.lane_pair}</div>
                <div class="timestamp">${snapshot.timestamp}</div>
            </div>
        `;

        gallery.insertBefore(snapshotDiv, gallery.firstChild);

        // Keep only the last 12 snapshots
        while (gallery.children.length > 12) {
            gallery.removeChild(gallery.lastChild);
        }
    }

    async loadCameraStatuses() {
        try {
            const response = await fetch('/camera/api/camera/config');
            const cameras = await response.json();
            
            for (const [cameraId, config] of Object.entries(cameras)) {
                this.updateCameraStatus(cameraId, 'checking');
                
                // Check camera status
                try {
                    const statusResponse = await fetch(`/camera/api/camera/${cameraId}/status`);
                    const status = await statusResponse.json();
                    this.updateCameraStatus(cameraId, status.error ? 'offline' : 'online');
                } catch {
                    this.updateCameraStatus(cameraId, 'offline');
                }
            }
        } catch (error) {
            console.error('Failed to load camera statuses:', error);
        }
    }

    updateCameraStatus(cameraId, status) {
        const statusElement = document.getElementById(`status-${cameraId}`);
        if (statusElement) {
            statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            statusElement.className = `status-indicator ${status}`;
        }
    }

    // Modal Management
    closeImportModal() {
        const modal = document.getElementById('import-cameras-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    openManualCameraModal() {
        const modal = document.getElementById('add-manual-camera-modal');
        if (modal) {
            modal.style.display = 'block';
        }
    }

    closeManualCameraModal() {
        const modal = document.getElementById('add-manual-camera-modal');
        if (modal) {
            modal.style.display = 'none';
            document.getElementById('manual-camera-form').reset();
        }
    }

    async addManualCamera(e) {
        e.preventDefault();
        
        const cameraData = {
            camera_id: `manual_${Date.now()}`,
            name: document.getElementById('manual-camera-name').value,
            ip: document.getElementById('manual-camera-ip').value,
            username: document.getElementById('manual-camera-username').value,
            password: document.getElementById('manual-camera-password').value,
            port: parseInt(document.getElementById('manual-camera-port').value),
            type: document.getElementById('manual-camera-type').value,
            lane_pair: document.getElementById('manual-camera-lane').value
        };

        // Validate required fields
        if (!cameraData.name || !cameraData.ip || !cameraData.username || !cameraData.password) {
            this.showMessage('Please fill in all required fields', 'error');
            return;
        }

        try {
            const response = await fetch('/camera/api/camera/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cameraData)
            });

            const result = await response.json();
            if (result.success) {
                this.showMessage('Camera added successfully', 'success');
                this.closeManualCameraModal();
                setTimeout(() => window.location.reload(), 1000);
            } else {
                this.showMessage(`Failed to add camera: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showMessage(`Add camera error: ${error.message}`, 'error');
        }
    }

    // Bowling-specific keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (!this.selectedCamera) return;

            // Only activate if not typing in an input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            switch(e.key.toLowerCase()) {
                case 'arrowup':
                case 'w':
                    e.preventDefault();
                    this.sendPTZCommand('up');
                    break;
                case 'arrowdown':
                case 's':
                    e.preventDefault();
                    this.sendPTZCommand('down');
                    break;
                case 'arrowleft':
                case 'a':
                    e.preventDefault();
                    this.sendPTZCommand('left');
                    break;
                case 'arrowright':
                case 'd':
                    e.preventDefault();
                    this.sendPTZCommand('right');
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    this.sendPTZCommand('zoom_in');
                    break;
                case '-':
                    e.preventDefault();
                    this.sendPTZCommand('zoom_out');
                    break;
                case ' ':
                    e.preventDefault();
                    this.takeSnapshot();
                    break;
                case 'l':
                    e.preventDefault();
                    this.toggleSpotlight();
                    break;
                // Quick presets 1-8
                case '1':
                    e.preventDefault();
                    this.executeQuickPreset('pin_deck');
                    break;
                case '2':
                    e.preventDefault();
                    this.executeQuickPreset('approach');
                    break;
                case '3':
                    e.preventDefault();
                    this.executeQuickPreset('player');
                    break;
                case '4':
                    e.preventDefault();
                    this.executeQuickPreset('wide');
                    break;
                case '5':
                    e.preventDefault();
                    this.executeQuickPreset('scoring');
                    break;
                case '6':
                    e.preventDefault();
                    this.executeQuickPreset('ball_return');
                    break;
                case '7':
                    e.preventDefault();
                    this.executeQuickPreset('settee');
                    break;
                case '8':
                    e.preventDefault();
                    this.executeQuickPreset('overview');
                    break;
            }
        });

        document.addEventListener('keyup', (e) => {
            if (!this.selectedCamera) return;
            
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Stop PTZ movement on key release
            if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', 'w', 'a', 's', 'd', '+', '=', '-'].includes(e.key.toLowerCase())) {
                this.sendPTZCommand('stop');
            }
        });
    }

    // Utility Methods
    showMessage(message, type = 'info') {
        const messagesContainer = document.getElementById('status-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message ${type}`;
        messageDiv.textContent = message;

        messagesContainer.appendChild(messageDiv);

        // Auto-remove message after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 5000);
    }

    // Auto-refresh camera statuses every 30 seconds
    startStatusMonitoring() {
        setInterval(() => {
            this.loadCameraStatuses();
        }, 30000);
    }
}

// Initialize bowling camera controller when page loads
document.addEventListener('DOMContentLoaded', () => {
    const controller = new BowlingCameraController();
    controller.setupKeyboardShortcuts();
    controller.startStatusMonitoring();
    
    // Make controller globally accessible for debugging
    window.bowlingCameraController = controller;
});