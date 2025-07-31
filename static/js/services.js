// /static/js/services.js - FIXED VERSION

const statusItems = document.getElementById("status-items");
const closeModal = document.getElementById("close-services-modal");
const servicesModal = document.getElementById("services-modal");

const tabs = ["system", "cameras", "livescores", "dhcp"];
let currentTab = "system";
let isLoading = false; // Prevent multiple simultaneous loads
let autoRefreshInterval = null; // Store interval reference

// Make switchTab globally accessible for onclick handlers
function switchTab(tab) {
  currentTab = tab;

  tabs.forEach(t => {
    document.getElementById(`tab-${t}`).classList.remove("active");
    if (t === "dhcp") {
      document.getElementById("tab-dhcp-content").style.display = "none";
    }
  });

  document.getElementById(`tab-${tab}`).classList.add("active");

  if (tab === "dhcp") {
    document.getElementById("tab-dhcp-content").style.display = "block";
    statusItems.innerHTML = ""; // Clear any loader
    loadDhcpConfig();
    populateNicDropdowns();
    stopAutoRefresh(); // Stop auto-refresh when on DHCP tab
  } else {
    document.getElementById("tab-dhcp-content").style.display = "none";
    renderStatusItems(); // This will show loader then load content
    startAutoRefresh(); // Start auto-refresh for other tabs
  }
}

// Make it globally accessible
window.switchTab = switchTab;

function createStatusRow(label, id, controls = false, tooltip = "") {
  const row = document.createElement("div");
  row.className = "status-item";
  row.id = `row-${id}`;

  const left = document.createElement("div");
  left.className = "status-label";
  left.textContent = label;
  if (tooltip) left.title = tooltip;

  const right = document.createElement("div");
  right.className = "status-right";

  if (controls) {
    const ctrl = document.createElement("div");
    ctrl.className = "service-controls";

    const startBtn = document.createElement("button");
    startBtn.textContent = "Start";
    startBtn.className = "btn-start";
    startBtn.onclick = () => controlService(id, "start");

    const stopBtn = document.createElement("button");
    stopBtn.textContent = "Stop";
    stopBtn.className = "btn-stop";
    stopBtn.onclick = () => controlService(id, "stop");

    const restartBtn = document.createElement("button");
    restartBtn.textContent = "Restart";
    restartBtn.className = "btn-restart";
    restartBtn.onclick = () => controlService(id, "restart");

    ctrl.appendChild(startBtn);
    ctrl.appendChild(stopBtn);
    ctrl.appendChild(restartBtn);
    right.appendChild(ctrl);
  }

  const light = document.createElement("div");
  light.className = "status-light red";
  light.id = `light-${id}`;
  right.appendChild(light);

  row.appendChild(left);
  row.appendChild(right);
  return row;
}

function updateLight(id, status) {
  const light = document.getElementById(`light-${id}`);
  if (light) {
    light.className = "status-light " + (status ? "green" : "red");
  }
}

function controlService(serviceId, action) {
  // Show a simple loading state instead of full bowling animation
  showSimpleLoading(`${action}ing ${serviceId}...`);
  
  fetch("/control_service", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service: serviceId, action })
  }).then(response => response.json())
    .then(data => {
      console.log("Service control response:", data);
      // Wait 2 seconds then refresh WITHOUT showing bowling animation
      setTimeout(() => {
        renderStatusItemsQuiet(); // New function that doesn't show loader
      }, 2000);
    })
    .catch(error => {
      console.error("Service control error:", error);
      renderStatusItemsQuiet();
    });
}

function renderStatusItems() {
  if (isLoading) {
    console.log("Already loading, skipping...");
    return;
  }
  
  isLoading = true;
  
  // Show bowling loader only on initial load or tab switch
  showBowlingLoader(getLoadingMessage());
  
  fetchAndRenderStatus()
    .finally(() => {
      isLoading = false;
    });
}

function renderStatusItemsQuiet() {
  // Refresh without showing the bowling animation
  if (isLoading) return;
  
  isLoading = true;
  showSimpleLoading("Refreshing...");
  
  fetchAndRenderStatus()
    .finally(() => {
      isLoading = false;
    });
}

function fetchAndRenderStatus() {
  return fetch("/get_service_status")
    .then(res => res.json())
    .then(data => {
      statusItems.innerHTML = "";

      if (currentTab === "system") {
        const checks = [
          ["Internet Connection", "internet"],
          ["Cornerpin Standings", "cornerpin"],
          ["OBS WebSocket", "obs"]
        ];
        checks.forEach(([label, id]) => {
          statusItems.appendChild(createStatusRow(label, id));
        });

        Object.entries(data.diagnostics || {}).forEach(([key, val]) => {
          const id = `diag-${key.replace(/\s+/g, "-").toLowerCase()}`;
          const row = createStatusRow(`${key}: ${val}`, id);
          row.querySelector(".status-light").style.display = "none";
          statusItems.appendChild(row);
        });
      }
      else if (currentTab === "cameras") {
        (data.camera_ips || []).forEach((ip, idx) => {
          const label = `Camera Lane ${idx * 2 + 1}&${idx * 2 + 2}`;
          statusItems.appendChild(createStatusRow(label, `cam${idx}`, false, `Ping ${ip}`));
        });
      }
      else if (currentTab === "livescores") {
        (data.livescores || []).forEach(({ id }, idx) => {
          const label = `Lane ${idx * 2 + 1}&${idx * 2 + 2} Livescores Polling Service`;
          statusItems.appendChild(createStatusRow(label, id, true));
        });
      }

      Object.entries(data.status || {}).forEach(([id, val]) => {
        updateLight(id, val);
      });
    })
    .catch(error => {
      console.error("Failed to fetch service status:", error);
      statusItems.innerHTML = '<div class="status-item"><div class="status-label">Error loading services</div></div>';
    });
}

function getLoadingMessage() {
  switch(currentTab) {
    case "system": return "Loading system status...";
    case "cameras": return "Checking camera connections...";
    case "livescores": return "Loading livescores services...";
    default: return "Loading...";
  }
}

// Modal controls
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("services-popup-btn").addEventListener("click", (e) => {
    e.preventDefault();
    servicesModal.style.display = "block";
    switchTab("system");
  });

  closeModal.addEventListener("click", () => {
    servicesModal.style.display = "none";
    stopAutoRefresh(); // Stop auto-refresh when modal closes
  });

  window.addEventListener("click", (e) => {
    if (e.target === servicesModal) {
      servicesModal.style.display = "none";
      stopAutoRefresh(); // Stop auto-refresh when modal closes
    }
  });

  document.getElementById("restart-system").addEventListener("click", () => {
    if (confirm("Are you sure you want to restart the system?")) {
      fetch("/restart_system", { method: "POST" });
    }
  });

  document.getElementById("shutdown-system").addEventListener("click", () => {
    if (confirm("Are you sure you want to shutdown the system?")) {
      fetch("/shutdown_system", { method: "POST" });
    }
  });

  // DHCP form buttons
  const saveBtn = document.getElementById("save-dhcp-btn");
  if (saveBtn) {
    saveBtn.onclick = saveDhcpConfig;
  }

  const restartBtn = document.getElementById("restart-dhcp-btn");
  if (restartBtn) {
    restartBtn.onclick = restartDhcpService;
  }

  const addSwitchBtn = document.getElementById("add-switch-btn");
  if (addSwitchBtn) {
    addSwitchBtn.onclick = () => addSwitchRow();
  }
});

// Auto-refresh management
function startAutoRefresh() {
  stopAutoRefresh(); // Clear any existing interval
  
  autoRefreshInterval = setInterval(() => {
    if (currentTab !== "dhcp" && servicesModal.style.display === "block" && !isLoading) {
      renderStatusItemsQuiet(); // Use quiet refresh for auto-refresh
    }
  }, 30000); // Every 30 seconds
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

// DHCP Functions
function loadDhcpConfig() {
  fetch("/get_dhcp_config")
    .then((res) => res.json())
    .then((config) => {
      populateDhcpRows(config.reservations || {});
    })
    .catch((err) => {
      console.error("Failed to load DHCP config", err);
      populateDhcpRows({});
    });
}

function populateDhcpRows(reservations) {
  const cameraTableBody = document.querySelector("#camera-reservations");
  const switchTableBody = document.querySelector("#switch-reservations");

  if (cameraTableBody) cameraTableBody.innerHTML = "";
  if (switchTableBody) switchTableBody.innerHTML = "";

  // Always show ALL camera lanes
  const allCameraLanes = [
    "Lane 1&2", "Lane 3&4", "Lane 5&6", "Lane 7&8", "Lane 9&10", "Lane 11&12",
    "Lane 13&14", "Lane 15&16", "Lane 17&18", "Lane 19&20", "Lane 21&22", "Lane 23&24"
  ];

  allCameraLanes.forEach(label => {
    const ip = deriveStaticIp(label);
    const mac = reservations[label] || "";

    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${label}</td>
      <td>${ip}</td>
      <td><input type="text" name="mac" data-label="${label}" value="${mac}" placeholder="00:11:22:33:44:55"></td>
      <td><span class="mac-status">🟡</span></td>
    `;

    if (cameraTableBody) {
      cameraTableBody.appendChild(row);
    }
  });

  // Only show switches that have existing MAC addresses
  Object.keys(reservations).forEach(label => {
    if (label.includes("Switch")) {
      addSwitchRow(label, reservations[label]);
    }
  });
}

function addSwitchRow(label = "", mac = "") {
  const switchTableBody = document.querySelector("#switch-reservations");
  if (!switchTableBody) return;

  // If no label provided, generate next available switch number
  if (!label) {
    const existingRows = switchTableBody.querySelectorAll("tr");
    const existingNumbers = Array.from(existingRows).map(row => {
      const labelCell = row.querySelector(".switch-label");
      if (labelCell) {
        const match = labelCell.value.match(/Switch (\d+)/);
        return match ? parseInt(match[1]) : 0;
      }
      return 0;
    });
    
    let nextNumber = 1;
    while (existingNumbers.includes(nextNumber)) {
      nextNumber++;
    }
    label = `Switch ${nextNumber}`;
  }

  // Calculate the IP based on switch number
  const switchMatch = label.match(/Switch (\d+)/);
  const switchNumber = switchMatch ? parseInt(switchMatch[1]) : 1;
  const ip = `192.168.83.${switchNumber * 2}`; // Switch 1 = .2, Switch 2 = .4, etc.

  const row = document.createElement("tr");
  row.innerHTML = `
    <td><input type="text" class="switch-label" value="${label}" placeholder="Switch Name"></td>
    <td>${ip}</td>
    <td><input type="text" name="mac" data-label="${label}" value="${mac}" placeholder="00:11:22:33:44:55"></td>
    <td>
      <span class="mac-status">🟡</span>
      <button type="button" class="remove-switch-btn" onclick="this.closest('tr').remove()">✕</button>
    </td>
  `;

  switchTableBody.appendChild(row);

  // Update data-label and IP when switch name changes
  const labelInput = row.querySelector(".switch-label");
  const macInput = row.querySelector("input[name='mac']");
  
  labelInput.addEventListener("input", (e) => {
    const newLabel = e.target.value;
    macInput.setAttribute("data-label", newLabel);
    
    // Update IP based on switch number
    const match = newLabel.match(/Switch (\d+)/);
    if (match) {
      const num = parseInt(match[1]);
      const newIp = `192.168.83.${num * 2}`;
      row.querySelector("td:nth-child(2)").textContent = newIp;
    }
  });
}

function deriveStaticIp(label) {
  const camera_map = {
    "Lane 1&2": "192.168.83.1", "Lane 3&4": "192.168.83.3", "Lane 5&6": "192.168.83.5",
    "Lane 7&8": "192.168.83.7", "Lane 9&10": "192.168.83.9", "Lane 11&12": "192.168.83.11",
    "Lane 13&14": "192.168.83.13", "Lane 15&16": "192.168.83.15", "Lane 17&18": "192.168.83.17",
    "Lane 19&20": "192.168.83.19", "Lane 21&22": "192.168.83.21", "Lane 23&24": "192.168.83.23"
  };
  
  if (label in camera_map) {
    return camera_map[label];
  }
  
  // For switches, calculate IP based on switch number
  const switchMatch = label.match(/Switch (\d+)/);
  if (switchMatch) {
    const switchNumber = parseInt(switchMatch[1]);
    return `192.168.83.${switchNumber * 2}`;
  }
  
  return "";
}

function saveDhcpConfig() {
  // Get all camera MAC inputs
  const cameraInputs = document.querySelectorAll("#camera-reservations input[name='mac']");
  
  // Get all switch inputs (including custom names)
  const switchRows = document.querySelectorAll("#switch-reservations tr");
  
  const lanNic = document.getElementById("lan-nic")?.value || "eth1";
  const wanNic = document.getElementById("wan-nic")?.value || "eth0";
  
  const reservations = {};
  
  // Process camera reservations
  cameraInputs.forEach((inp) => {
    const label = inp.dataset.label;
    const mac = inp.value.trim();
    if (mac) {
      reservations[label] = mac;
    }
  });

  // Process switch reservations (including custom names)
  switchRows.forEach(row => {
    const labelInput = row.querySelector(".switch-label");
    const macInput = row.querySelector("input[name='mac']");
    
    if (labelInput && macInput) {
      const label = labelInput.value.trim();
      const mac = macInput.value.trim();
      
      if (label && mac) {
        reservations[label] = mac;
      }
    }
  });

  const config = {
    lan_nic: lanNic,
    wan_nic: wanNic,
    lan_ip: "192.168.83.83",
    subnet: "255.255.255.0",
    range_start: "192.168.83.100",
    range_end: "192.168.83.200",
    reservations
  };

  fetch("/save_dhcp_config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        alert("DHCP config saved and dnsmasq restarted.");
      } else {
        alert("Failed to save DHCP config: " + (data.error || "Unknown error"));
      }
    })
    .catch((err) => {
      console.error("DHCP save error:", err);
      alert("Error saving DHCP config: " + err);
    });
}

function restartDhcpService() {
  fetch("/control_service", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service: "dnsmasq", action: "restart" })
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "ok") {
        alert("DHCP service restarted successfully.");
      } else {
        alert("Failed to restart DHCP service: " + (data.error || "Unknown error"));
      }
    })
    .catch((err) => {
      console.error("DHCP restart error:", err);
      alert("Restart failed: " + err);
    });
}

function populateNicDropdowns() {
  fetch("/get_nics")
    .then(res => res.json())
    .then(data => {
      const lanNicSelect = document.getElementById("lan-nic");
      const wanNicSelect = document.getElementById("wan-nic");

      if (lanNicSelect && wanNicSelect) {
        // Clear existing options
        lanNicSelect.innerHTML = "";
        wanNicSelect.innerHTML = "";

        // Add NIC options
        (data.nics || []).forEach(nic => {
          const opt1 = new Option(nic, nic);
          const opt2 = new Option(nic, nic);
          lanNicSelect.appendChild(opt1);
          wanNicSelect.appendChild(opt2);
        });

        // Set saved values
        lanNicSelect.value = data.config?.lan || "";
        wanNicSelect.value = data.config?.wan || "";
      }
    })
    .catch(err => {
      console.error("Failed to load NICs:", err);
    });
}

// Add these to your DOMContentLoaded section
const startDhcpBtn = document.getElementById("start-dhcp-btn");
if (startDhcpBtn) {
  startDhcpBtn.onclick = startDhcpServer;
}

const stopDhcpBtn = document.getElementById("stop-dhcp-btn");
if (stopDhcpBtn) {
  stopDhcpBtn.onclick = stopDhcpServer;
}

// Add these functions at the end of your services.js
function startDhcpServer() {
  if (confirm("Start DHCP server? This will take over DHCP on your network!")) {
    controlService("dnsmasq", "start");
  }
}

function stopDhcpServer() {
  controlService("dnsmasq", "stop");
}

function showBowlingLoader(message = "Loading services...") {
  statusItems.innerHTML = `
    <div class="bowling-loader">
      <div class="bowling-lane">
        <div class="bowling-ball"></div>
        <div class="bowling-pins">
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
          <div class="pin"></div>
        </div>
      </div>
      <div class="loading-text">${message}</div>
    </div>
  `;
}

function showSimpleLoading(message = "Loading...") {
  statusItems.innerHTML = `
    <div class="status-item">
      <div class="status-label">${message}</div>
      <div class="status-right">
        <div class="status-light" style="background: #ffa500; animation: pulse 1s infinite;"></div>
      </div>
    </div>
  `;
}

function hideBowlingLoader() {
  // This will be called when content is loaded
  // The loader gets replaced by actual content
}

// Add these to your DOMContentLoaded section
document.addEventListener("DOMContentLoaded", () => {
  const startDhcpBtn = document.getElementById("start-dhcp-btn");
  if (startDhcpBtn) {
    startDhcpBtn.onclick = startDhcpServer;
  }

  const stopDhcpBtn = document.getElementById("stop-dhcp-btn");
  if (stopDhcpBtn) {
    stopDhcpBtn.onclick = stopDhcpServer;
  }
});