// /static/js/tweak.js - Enhanced with GPU monitoring

document.addEventListener("DOMContentLoaded", function () {
  const openBtn = document.getElementById("tweak-popup-btn");
  const modal = document.getElementById("tweak-modal");
  const closeBtn = document.getElementById("close-tweak-modal");
  const form = document.getElementById("tweak-form");
  const refreshGpuBtn = document.getElementById("refresh-gpu");

  if (!openBtn || !modal || !closeBtn) {
    console.warn("❌ RTMP Tweak modal elements missing");
    return;
  }

  // Modal open/close functionality
  openBtn.addEventListener("click", function (e) {
    e.preventDefault();
    modal.classList.add("show");
    loadGpuData(); // Load GPU data when modal opens
    loadCurrentSettings(); // Load current RTMP settings
  });

  closeBtn.addEventListener("click", function () {
    modal.classList.remove("show");
  });

  window.addEventListener("click", function (e) {
    if (e.target === modal) {
      modal.classList.remove("show");
    }
  });

  // GPU refresh button
  if (refreshGpuBtn) {
    refreshGpuBtn.addEventListener("click", loadGpuData);
  }

  // Form submission
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      saveSettings();
    });
  }

  // Load current RTMP settings
  async function loadCurrentSettings() {
    try {
      const response = await fetch('/api/rtmp/settings');
      if (response.ok) {
        const settings = await response.json();
        populateForm(settings);
      }
    } catch (error) {
      console.warn("Could not load current settings:", error);
    }
  }

  // Populate form with current settings
  function populateForm(settings) {
    Object.keys(settings).forEach(key => {
      const element = document.getElementById(key);
      if (element) {
        element.value = settings[key];
      }
    });
  }

  // Save RTMP settings
  async function saveSettings() {
    const formData = new FormData(form);
    const settings = Object.fromEntries(formData.entries());

    try {
      const response = await fetch('/api/rtmp/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        showNotification("✅ RTMP settings saved successfully!", "success");
        modal.classList.remove("show");
      } else {
        showNotification("❌ Failed to save settings", "error");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      showNotification("❌ Network error occurred", "error");
    }
  }

  // Load GPU monitoring data
  async function loadGpuData() {
    const gpuStatus = document.getElementById("gpu-status");
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

  // Display GPU data in user-friendly format
  function displayGpuData(data) {
    const gpuStatus = document.getElementById("gpu-status");
    
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
          <div class="gpu-metric">
            <span class="label">Utilization:</span>
            <span class="value">${utilizationPercent}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${utilizationPercent}%"></div>
          </div>
          
          <div class="gpu-metric">
            <span class="label">Memory:</span>
            <span class="value">${gpu.memory_used}MB / ${gpu.memory_total}MB</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${memoryPercent}%"></div>
          </div>
          
          <div class="gpu-metric">
            <span class="label">Temperature:</span>
            <span class="value" style="color: ${temperatureColor}">${gpu.temperature}°C</span>
          </div>
          
          <div class="gpu-metric">
            <span class="label">Power:</span>
            <span class="value">${gpu.power_draw}W / ${gpu.power_limit}W</span>
          </div>
          
          <div class="gpu-metric">
            <span class="label">Clock:</span>
            <span class="value">${gpu.clocks_current || 'N/A'} MHz</span>
          </div>
          
          <div class="gpu-metric">
            <span class="label">NVENC Sessions:</span>
            <span class="value">${gpu.encoder_sessions || 0} active</span>
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

  // Show notification to user
  function showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
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

    // Remove after 3 seconds
    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  // Auto-refresh GPU data every 10 seconds when modal is open
  setInterval(() => {
    if (modal.classList.contains("show")) {
      loadGpuData();
    }
  }, 10000);
});

// Add CSS animations for notifications
const style = document.createElement('style');
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