// /static/js/advertising.js - MINIMAL FIX - Only fix what's broken
console.log("ADVERTISING.JS LOADED AND EXECUTING!");

document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM LOADED, SETTING UP EVENT LISTENERS");
  
  // Upload modal open/close
  const openBtn = document.getElementById('open-upload-modal');
  const closeBtn = document.getElementById('close-upload-modal');
  const modal = document.getElementById('upload-modal');

  console.log("Upload button:", openBtn);
  console.log("Upload modal:", modal);

  if (openBtn && modal) {
    openBtn.addEventListener('click', function () {
      console.log("UPLOAD BUTTON CLICKED!");
      modal.classList.remove('hidden');
      modal.style.display = 'block';  // Added this line
    });
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener('click', function () {
      modal.classList.add('hidden');
      modal.style.display = 'none';   // Added this line
    });
  }

  // Config modal open/close
  const configOpen = document.getElementById('open-config-modal');
  const configClose = document.getElementById('close-config-modal');
  const configModal = document.getElementById('config-modal');

  console.log("Config button:", configOpen);
  console.log("Config modal:", configModal);

  if (configOpen && configModal) {
    configOpen.addEventListener('click', function() {
      console.log("CONFIG BUTTON CLICKED!");
      configModal.classList.remove('hidden');
      configModal.style.display = 'block';  // Added this line
    });
  }

  if (configClose && configModal) {
    configClose.addEventListener('click', function() {
      configModal.classList.add('hidden');
      configModal.style.display = 'none';   // Added this line
    });
  }

  // Close modals when clicking outside
  window.addEventListener('click', function (e) {
    if (e.target === modal) {
      modal.classList.add('hidden');
      modal.style.display = 'none';  // Added this line
    }
    if (e.target === configModal) {
      configModal.classList.add('hidden');
      configModal.style.display = 'none';  // Added this line
    }
  });

  // Toggle image duration field
  const adFileInput = document.getElementById('ad_file');
  const durationDiv = document.getElementById('ad-duration-field');
  if (adFileInput && durationDiv) {
    adFileInput.addEventListener('change', function () {
      const fileName = this.value.toLowerCase();
      const ext = fileName.split('.').pop();
      const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp'].includes(ext);
      if (isImage) {
        durationDiv.classList.remove('hidden');
      } else {
        durationDiv.classList.add('hidden');
      }
    });
  }

  // Toggle TEAM/CUP mode visibility
  const modeSelect = document.getElementById("ad-mode-select");
  const teamSection = document.getElementById("team-mode-fields");
  const cupSection = document.getElementById("cup-mode-fields");

  function updateModeVisibility() {
    if (!modeSelect || !teamSection || !cupSection) return;
    const isTeam = modeSelect.value === "TEAM";
    teamSection.style.display = isTeam ? "block" : "none";
    cupSection.style.display = isTeam ? "none" : "block";
  }

  if (modeSelect) {
    modeSelect.addEventListener("change", updateModeVisibility);
    updateModeVisibility(); // initial load
  }

  // Toggle halfway ad fields visibility
  function toggleHalfwayFields(checkId, fieldClass) {
    const checkbox = document.getElementById(checkId);
    const fields = document.querySelectorAll("." + fieldClass);
    if (checkbox && fields.length) {
      const update = () => {
        fields.forEach(f => f.style.display = checkbox.checked ? "block" : "none");
      };
      checkbox.addEventListener("change", update);
      update(); // initial
    }
  }

  toggleHalfwayFields("team-halfway-check", "team-halfway-fields");
  toggleHalfwayFields("cup-halfway-check", "cup-halfway-fields");

  // Auto-hide flash messages after 5 seconds
  const flashMessages = document.querySelectorAll(".flash");
  flashMessages.forEach(msg => {
    setTimeout(() => {
      msg.style.opacity = "0";
      msg.style.transition = "opacity 0.5s ease";
      setTimeout(() => msg.remove(), 500);
    }, 5000); // 5 seconds
  });

  console.log("ALL EVENT LISTENERS SET UP!");
});