// /static/js/tweak.js - ENHANCED VERSION with per-stream settings

document.addEventListener("DOMContentLoaded", function () {
  const openBtn = document.getElementById("tweak-popup-btn");
  const modal = document.getElementById("tweak-modal");
  const closeBtn = document.getElementById("close-tweak-modal");

  if (!openBtn || !modal || !closeBtn) {
    console.warn("❌ RTMP Tweak modal elements missing");
    return;
  }

  // Modal open/close functionality
  openBtn.addEventListener("click", function (e) {
    e.preventDefault();
    modal.classList.add("show");
    loadModalData();
  });

  closeBtn.addEventListener("click", function (e) {
    e.preventDefault();
    modal.classList.remove("show");
  });

  window.addEventListener("click", function (e) {
    if (e.target === modal) {
      modal.classList.remove("show");
    }
  });

  // Load all modal data when opened
  async function loadModalData() {
    await Promise.all([
      loadGpuData(),
      loadMultiRtmpStatus(),
      loadEnabledStreams(),
      loadCurrentSettings()
    ]);
  }

  // Load enabled streams from dashboard config
  async function loadEnabledStreams() {
    try {
      const response = await fetch('/api/streams');
      if (response.ok) {
        const data = await response.json();
        const enabledStreams = data.streams || [];
        buildStreamTabs(enabledStreams);
      }
    } catch (error) {
      console.error("Failed to load enabled streams:", error);
      // Build with empty streams if API fails
      buildStreamTabs([]);
    }
  }

  // Build stream tabs for per-stream settings
  function buildStreamTabs(streams) {
    const tabsContainer = document.getElementById("stream-tabs");
    const settingsContainer = document.getElementById("stream-settings");
    
    if (!tabsContainer || !settingsContainer) {
      console.warn("Stream tabs containers not found");
      return;
    }

    // Clear existing content
    tabsContainer.innerHTML = '';
    settingsContainer.innerHTML = '';

    // Add Universal Settings tab first
    tabsContainer.innerHTML += `
      <div class="stream-tab active" data-stream="universal">
        🌐 Universal Settings
      </div>
    `;

    // Add individual stream tabs
    streams.forEach((stream) => {
      tabsContainer.innerHTML += `
        <div class="stream-tab" data-stream="${stream.name}">
          ${stream.name}
        </div>
      `;
    });

    // Add Universal Settings panel
    settingsContainer.innerHTML = `
      <div class="stream-panel active" data-stream="universal">
        <div class="universal-toggle">
          <label>
            <input type="checkbox" id="universal-settings" checked>
            Apply same settings to all streams
          </label>
        </div>
        ${buildSettingsForm('universal')}
      </div>
    `;

    // Add individual stream panels
    streams.forEach(stream => {
      settingsContainer.innerHTML += `
        <div class="stream-panel" data-stream="${stream.name}">
          <h4>Settings for ${stream.name}</h4>
          ${buildSettingsForm(stream.name)}
        </div>
      `;
    });

    // Setup tab switching
    setupTabSwitching();
    setupUniversalToggle();
  }

  // Build settings form for a stream
  function buildSettingsForm(streamId) {
    return `
      <form class="rtmp-settings-form" data-stream="${streamId}">
        <div class="form-grid">
          <div class="form-group">
            <label>Encoder</label>
            <select name="encoder" class="form-control">
              <option value="obs_x264">x264 (CPU)</option>
              <option value="obs_nvenc">NVENC (GPU)</option>
            </select>
            <small>Choose encoding hardware</small>
          </div>
          
          <div class="form-group">
            <label>Bitrate (kbps)</label>
            <input type="number" name="bitrate" min="1000" max="20000" step="100" value="6000" class="form-control">
            <small>Stream quality control</small>
          </div>
          
          <div class="form-group">
            <label>Rate Control</label>
            <select name="rate_control" class="form-control">
              <option value="CBR">CBR</option>
              <option value="VBR">VBR</option>
              <option value="CQP">CQP</option>
            </select>
            <small>Bitrate management</small>
          </div>
          
          <div class="form-group">
            <label>Preset</label>
            <select name="preset" class="form-control">
              <option value="ultrafast">ultrafast</option>
              <option value="superfast">superfast</option>
              <option value="veryfast">veryfast</option>
              <option value="faster">faster</option>
              <option value="fast">fast</option>
              <option value="medium">medium</option>
              <option value="slow">slow</option>
              <option value="slower">slower</option>
              <option value="veryslow">veryslow</option>
              <option value="p1">p1 (Max Performance)</option>
              <option value="p5" selected>p5 (Quality)</option>
            </select>
            <small>Speed vs quality</small>
          </div>
          
          <div class="form-group">
            <label>Profile</label>
            <select name="profile" class="form-control">
              <option value="baseline">baseline</option>
              <option value="main">main</option>
              <option value="high" selected>high</option>
            </select>
            <small>Compatibility level</small>
          </div>
          
          <div class="form-group">
            <label>GPU Index</label>
            <input type="number" name="gpu" min="0" value="0" class="form-control">
            <small>GPU device selection</small>
          </div>
          
          <div class="form-group">
            <label>Max B-frames</label>
            <input type="number" name="bf" min="0" max="4" value="2" class="form-control">
            <small>Compression frames</small>
          </div>
          
          <div class="form-group">
            <label>Keyframe Interval</label>
            <input type="number" name="keyint_sec" min="1" max="10" value="2" class="form-control">
            <small>Seconds between keyframes</small>
          </div>
        </div>
      </form>
    `;
  }

  // Setup tab switching functionality
  function setupTabSwitching() {
    const tabs = document.querySelectorAll('.stream-tab');
    const panels = document.querySelectorAll('.stream-panel');

    tabs.forEach(tab => {
      tab.addEventListener('click', function() {
        const streamName = this.dataset.stream;
        
        // Update active tab
        tabs.forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        
        // Update active panel
        panels.forEach(p => p.classList.remove('active'));
        const activePanel = document.querySelector(`.stream-panel[data-stream="${streamName}"]`);
        if (activePanel) {
          activePanel.classList.add('active');
        }
      });
    });
  }

  // Setup universal settings toggle
  function setupUniversalToggle() {
    const universalCheckbox = document.getElementById('universal-settings');
    const streamTabs = document.querySelectorAll('.stream-tab:not([data-stream="universal"])');
    
    if (universalCheckbox) {
      universalCheckbox.addEventListener('change', function() {
        streamTabs.forEach(tab => {
          tab.style.display = this.checked ? 'none' : 'block';
        });
      });
    }
  }

  // Load Multi-RTMP status
  async function loadMultiRtmpStatus() {
    const statusDiv = document.getElementById("multi-rtmp-status");
    if (!statusDiv) return;
    
    statusDiv.innerHTML = '<div class="status-loading">Loading Multi-RTMP status...</div>';
    
    try {
      const response = await fetch('/api/multi-rtmp/status');
      if (response.ok) {
        const data = await response.json();
        displayMultiRtmpStatus(data);
      } else {
        statusDiv.innerHTML = '<div class="status-error">Failed to load Multi-RTMP status</div>';
      }
    } catch (error) {
      console.error("Error loading Multi-RTMP status:", error);
      statusDiv.innerHTML = '<div class="status-error">Multi-RTMP connection error</div>';
    }
  }

  // Display Multi-RTMP status
  function displayMultiRtmpStatus(data) {
    const statusDiv = document.getElementById("multi-rtmp-status");
    if (!statusDiv) return;

    let html = '';
    
    if (data.outputs && data.outputs.length > 0) {
      html += '<div class="rtmp-outputs">';
      data.outputs.forEach(output => {
        const statusClass = output.enabled ? 'status-active' : 'status-inactive';
        const statusText = output.enabled ? 'Active' : 'Inactive';
        html += `
          <div class="rtmp-output ${statusClass}">
            <span class="output-name">${output.name}</span>
            <span class="output-status">${statusText}</span>
            <span class="output-encoder">${output.settings?.encoder || 'Unknown'}</span>
            <span class="output-bitrate">${output.settings?.bitrate || 'Unknown'}k</span>
          </div>
        `;
      });
      html += '</div>';
    } else {
      html += '<div class="status-info">No active RTMP outputs configured</div>';
    }
    
    statusDiv.innerHTML = html;
  }

  // Load GPU monitoring data
  async function loadGpuData() {
    const gpuStatus = document.getElementById("gpu-status");
    if (!gpuStatus) return;
    
    gpuStatus.innerHTML = '<div class="gpu-loading">Loading GPU information...</div>';

    try {
      const response = await fetch('/api/gpu/status');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      displayGpuData(data);
    } catch (error) {
      console.error("Error loading GPU data:", error);
      gpuStatus.innerHTML = '<div class="gpu-error">❌ Failed to load GPU data</div>';
    }
  }

  // Display GPU data
  function displayGpuData(data) {
    const gpuStatus = document.getElementById("gpu-status");
    if (!gpuStatus) return;
    
    if (!data.gpus || data.gpus.length === 0) {
      gpuStatus.innerHTML = '<div class="gpu-error">No NVIDIA GPUs detected</div>';
      return;
    }

    let html = '';
    data.gpus.forEach((gpu, index) => {
      const utilizationPercent = parseInt(gpu.utilization || 0);
      const memoryPercent = Math.round((gpu.memory_used / gpu.memory_total) * 100);
      const temperatureColor = getTemperatureColor(gpu.temperature);

      html += `
        <div class="gpu-card">
          <h5>🎮 ${gpu.name}</h5>
          <div class="gpu-metrics">
            <div class="gpu-metric">
              <span class="label">GPU Load:</span>
              <span class="value">${utilizationPercent}%</span>
              <div class="progress-bar">
                <div class="progress-fill" style="width: ${utilizationPercent}%"></div>
              </div>
            </div>
            
            <div class="gpu-metric">
              <span class="label">VRAM:</span>
              <span class="value">${gpu.memory_used}MB / ${gpu.memory_total}MB</span>
              <div class="progress-bar">
                <div class="progress-fill" style="width: ${memoryPercent}%"></div>
              </div>
            </div>
            
            <div class="gpu-metric">
              <span class="label">Temperature:</span>
              <span class="value" style="color: ${temperatureColor}">${gpu.temperature}°C</span>
            </div>
            
            <div class="gpu-metric">
              <span class="label">NVENC Sessions:</span>
              <span class="value nvenc-sessions">${gpu.encoder_sessions || 0} active</span>
            </div>
          </div>
        </div>
      `;
    });

    gpuStatus.innerHTML = html;
  }

  // Get color based on temperature
  function getTemperatureColor(temp) {
    if (temp < 60) return "#4f4";      // Green - cool
    if (temp < 75) return "#ff4";      // Yellow - warm  
    if (temp < 85) return "#f84";      // Orange - hot
    return "#f44";                     // Red - very hot
  }

  // Load current RTMP settings
  async function loadCurrentSettings() {
    try {
      const response = await fetch('/api/rtmp/settings');
      if (response.ok) {
        const settings = await response.json();
        populateSettings(settings);
      }
    } catch (error) {
      console.warn("Could not load current settings:", error);
    }
  }

  // Populate form with current settings (handle both old and new format)
  function populateSettings(settings) {
    // Check if this is new format with universal/streams structure
    if (settings.universal !== undefined || settings.streams) {
      // New format with per-stream settings
      if (settings.universal && settings.universal_settings) {
        const universalForm = document.querySelector('.stream-panel[data-stream="universal"] form');
        if (universalForm) {
          populateForm(universalForm, settings.universal_settings);
        }
      }
      
      if (settings.streams) {
        Object.keys(settings.streams).forEach(streamName => {
          const streamForm = document.querySelector(`.stream-panel[data-stream="${streamName}"] form`);
          if (streamForm) {
            populateForm(streamForm, settings.streams[streamName]);
          }
        });
      }
    } else {
      // Old format - populate universal form
      const universalForm = document.querySelector('.stream-panel[data-stream="universal"] form');
      if (universalForm) {
        populateForm(universalForm, settings);
      }
    }
  }

  // Populate individual form
  function populateForm(form, settings) {
    Object.keys(settings).forEach(key => {
      const element = form.querySelector(`[name="${key}"]`);
      if (element) {
        element.value = settings[key];
      }
    });
  }

  // Save RTMP settings
  window.saveRtmpSettings = async function() {
    const universalCheckbox = document.getElementById('universal-settings');
    const isUniversal = universalCheckbox ? universalCheckbox.checked : true;
    
    let settings = {
      universal: isUniversal,
      timestamp: Date.now()
    };

    if (isUniversal) {
      // Get universal settings
      const universalForm = document.querySelector('.stream-panel[data-stream="universal"] form');
      if (universalForm) {
        settings.universal_settings = getFormData(universalForm);
      }
    } else {
      // Get per-stream settings
      settings.streams = {};
      const streamForms = document.querySelectorAll('.stream-panel:not([data-stream="universal"]) form');
      streamForms.forEach(form => {
        const streamName = form.closest('[data-stream]').dataset.stream;
        settings.streams[streamName] = getFormData(form);
      });
    }

    try {
      showNotification("💾 Saving RTMP settings...", "info");
      
      const response = await fetch('/api/rtmp/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        const result = await response.json();
        showNotification("✅ RTMP settings applied to OBS successfully!", "success");
        
        // Reload Multi-RTMP status to show changes
        setTimeout(() => {
          loadMultiRtmpStatus();
          loadGpuData(); // Refresh GPU data to show new encoder load
        }, 1000);
      } else {
        const error = await response.text();
        showNotification("❌ Failed to apply settings: " + error, "error");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      showNotification("❌ Network error occurred", "error");
    }
  };

  // Get form data as object
  function getFormData(form) {
    const formData = new FormData(form);
    const data = {};
    for (let [key, value] of formData.entries()) {
      data[key] = value;
    }
    return data;
  }

  // Show notification to user
  function showNotification(message, type = "info") {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.rtmp-notification');
    existingNotifications.forEach(n => n.remove());

    // Create notification element
    const notification = document.createElement("div");
    notification.className = `rtmp-notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${type === 'success' ? '#1f8f1f' : type === 'error' ? '#8f1f1f' : '#1f5f8f'};
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      z-index: 10001;
      font-weight: bold;
      animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);

    // Remove after 4 seconds
    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 4000);
  }

  // Refresh functions for buttons
  window.refreshGpuData = loadGpuData;
  window.refreshMultiRtmpStatus = loadMultiRtmpStatus;

  // Auto-refresh GPU and Multi-RTMP status every 15 seconds when modal is open
  setInterval(() => {
    if (modal.classList.contains("show")) {
      loadGpuData();
      loadMultiRtmpStatus();
    }
  }, 15000);
});

// Add CSS animations for notifications
if (!document.getElementById('rtmp-animations-style')) {
  const style = document.createElement('style');
  style.id = 'rtmp-animations-style';
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
}