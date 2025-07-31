document.addEventListener('DOMContentLoaded', function () {
  const laneCount = document.querySelectorAll('.stream-panel').length;
  
  // Prevent infinite submission loops
  let isSubmitting = false;
  const configForm = document.getElementById('config-form');
  
  if (configForm) {
    configForm.addEventListener('submit', (e) => {
      if (isSubmitting) {
        e.preventDefault();
        return false;
      }
      isSubmitting = true;
      console.log('Config form submitted');
      
      // Reset flag after reasonable time
      setTimeout(() => {
        isSubmitting = false;
      }, 2000);
    });
  }

  function validateRtspField(field) {
    const value = field.value.trim();
    if (value && !value.startsWith('rtsp://')) {
      alert('RTSP URL must start with rtsp://');
      field.value = '';
    }
  }

  // Load video devices once and cache
  let videoDevicesLoaded = false;
  fetch('/get_video_devices')
    .then(res => {
      if (!res.ok) {
        console.error('Failed to fetch video devices:', res.status);
        return [];
      }
      return res.json();
    })
    .then(videoDevices => {
      window.availableVideoDevices = videoDevices || [];
      videoDevicesLoaded = true;
      refreshAllDropdowns();
    })
    .catch(err => {
      console.error('Fetch error for video devices:', err);
      window.availableVideoDevices = [];
      videoDevicesLoaded = true;
    });

  function clearVideoSelections() {
    const allSelects = document.querySelectorAll(
      'select.camera-select-dropdown, select.pin-local-field, select.player-local-field'
    );
    allSelects.forEach(select => {
      select.value = '';
      select.dataset.selected = '';
    });
    refreshAllDropdowns();
  }

  function setupDeviceDropdown(select, currentValue) {
    if (!videoDevicesLoaded || !window.availableVideoDevices) return;
    
    const allSelects = document.querySelectorAll(
      'select.camera-select-dropdown, select.pin-local-field, select.player-local-field'
    );
    const usedDevices = new Set();
    allSelects.forEach(s => {
      if (s !== select && s.value) usedDevices.add(s.value);
    });

    select.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '-- Select Camera --';
    placeholder.selected = !currentValue || currentValue === '';
    select.appendChild(placeholder);

    window.availableVideoDevices.forEach(dev => {
      const opt = document.createElement('option');
      opt.value = dev.id;
      opt.textContent = dev.label;
      if (usedDevices.has(dev.id) && dev.id !== currentValue) {
        opt.disabled = true;
        opt.textContent += ' (in use)';
      }
      if (dev.id === currentValue) opt.selected = true;
      select.appendChild(opt);
    });
  }

  function refreshAllDropdowns() {
    if (!videoDevicesLoaded) return;
    
    const allSelects = document.querySelectorAll(
      'select.camera-select-dropdown, select.pin-local-field, select.player-local-field'
    );
    allSelects.forEach(select => {
      setupDeviceDropdown(select, select.value || '');
    });
  }

  // Initialize each lane panel
  for (let i = 0; i < laneCount; i++) {
    const panel = document.getElementById(`panel-lane${i}`);
    if (!panel) continue;

    // Set saved delay value (if any)
    const delayInput = panel.querySelector(`#lane${i}_video_delay_ms`);
    if (delayInput) {
      const saved = delayInput.getAttribute('value');
      if (saved) delayInput.value = saved;
    }

    // Source type switching (RTSP vs Local)
    const rtspDiv = panel.querySelector('.rtsp-field');
    const localDiv = panel.querySelector('.local-field');
    const radios = panel.querySelectorAll(`input[name="lane${i}_src_type"]`);
    const mainSelect = panel.querySelector(`select[name="lane${i}_local_src"]`);
    
    function toggleSrc() {
      const checkedRadio = panel.querySelector(`input[name="lane${i}_src_type"]:checked`);
      if (!checkedRadio || !rtspDiv || !localDiv) return;
      const sel = checkedRadio.value;
      rtspDiv.style.display = sel === 'rtsp' ? 'block' : 'none';
      localDiv.style.display = sel === 'local' ? 'block' : 'none';
      if (sel === 'rtsp' && mainSelect) {
        mainSelect.value = '';
        refreshAllDropdowns();
      }
    }
    
    // Clean event listeners
    radios.forEach(r => {
      const newRadio = r.cloneNode(true);
      r.parentNode.replaceChild(newRadio, r);
      newRadio.addEventListener('change', toggleSrc);
    });
    toggleSrc();

    // Pin camera configuration
    const pinToggle = panel.querySelector(`input[name="lane${i}_enable_pin_cam"]`);
    const pinBlock = panel.querySelector('.pin-cam-config');
    const pinTypeRadios = panel.querySelectorAll(`input[name="lane${i}_pin_cam_type"]`);
    const pinRtsp = panel.querySelector('.pin-rtsp-field');
    const pinLocal = panel.querySelector('.pin-local-field');
    const pinSelect = panel.querySelector(`select[name="lane${i}_pin_local"]`);

    // Player camera configuration
    const playerToggle = panel.querySelector(`input[name="lane${i}_enable_player_cam"]`);
    const playerBlock = panel.querySelector('.player-cam-config');
    const playerTypeRadios = panel.querySelectorAll(`input[name="lane${i}_player_cam_type"]`);
    const playerRtsp = panel.querySelector('.player-rtsp-field');
    const playerLocal = panel.querySelector('.player-local-field');
    const playerSelect = panel.querySelector(`select[name="lane${i}_player_local"]`);

      function toggleOptionalBlock(checkbox, block) {
    if (!checkbox || !block) return;

    function handleToggle() {
      if (checkbox.checked) {
        block.classList.remove('hidden');
        block.style.display = 'block';
        
        // Get fresh references after making visible
        const radios = block.querySelectorAll('input[type="radio"]');
        const rtspField = block.querySelector('.pin-rtsp-field, .player-rtsp-field');
        const localField = block.querySelector('.pin-local-field, .player-local-field');
        const select = block.querySelector('select');
        
        // Setup radio toggle behavior
        function toggleFields() {
          const checkedRadio = [...radios].find(r => r.checked);
          if (!checkedRadio) return;
          
          const selected = checkedRadio.value;
          rtspField.style.display = selected === 'rtsp' ? 'block' : 'none';
          localField.style.display = selected === 'local' ? 'block' : 'none';
          
          if (selected === 'local' && select) {
            setupDeviceDropdown(select, select.dataset.selected || '');
          }
        }
        
        // Bind radio events
        radios.forEach(r => {
          r.addEventListener('change', toggleFields);
        });
        
        // Initial setup
        toggleFields();
        
      } else {
        block.classList.add('hidden');
        block.style.display = 'none';
      }
    }
    
    checkbox.addEventListener('change', handleToggle);
    handleToggle();
  }
  
    // Apply configurations
    const newPinToggle = toggleOptionalBlock(pinToggle, pinBlock);
    const newPlayerToggle = toggleOptionalBlock(playerToggle, playerBlock);

    // Setup device dropdowns
    if (mainSelect) {
      setupDeviceDropdown(mainSelect, mainSelect.value || mainSelect.dataset.selected || '');
      mainSelect.addEventListener('change', refreshAllDropdowns);
    }
    if (pinSelect) {
      setupDeviceDropdown(pinSelect, pinSelect.value || pinSelect.dataset.selected || '');
      pinSelect.addEventListener('change', refreshAllDropdowns);
    }
    if (playerSelect) {
      setupDeviceDropdown(playerSelect, playerSelect.value || playerSelect.dataset.selected || '');
      playerSelect.addEventListener('change', refreshAllDropdowns);
    }

    // RTSP validation
    const rtspInputs = panel.querySelectorAll('.rtsp-field input, .pin-rtsp-field input, .player-rtsp-field input');
    rtspInputs.forEach(input => {
      input.addEventListener('blur', () => validateRtspField(input));
    });

    // Scoring/overlay configuration
    const scoringDropdown = panel.querySelector(`#lane${i}_scoring_type`);
    const livescoreDiv = panel.querySelector(`#livescores-settings-${i}`);
    const localOverlayDiv = panel.querySelector(`#local-overlay-inputs-${i}`);
    const oddField = panel.querySelector(`#lane${i}_odd_lane_src`);
    const evenField = panel.querySelector(`#lane${i}_even_lane_src`);
    
    function toggleOverlayFields() {
      if (!scoringDropdown) return;
      
      if (scoringDropdown.value === 'livescores') {
        if (livescoreDiv) livescoreDiv.style.display = 'block';
        if (localOverlayDiv) localOverlayDiv.style.display = 'block';
        if (oddField) oddField.readOnly = true;
        if (evenField) evenField.readOnly = true;
      } else {
        if (livescoreDiv) livescoreDiv.style.display = 'none';
        if (localOverlayDiv) localOverlayDiv.style.display = 'block';
        if (oddField) oddField.readOnly = false;
        if (evenField) evenField.readOnly = false;
      }
    }
    
    if (scoringDropdown) {
      scoringDropdown.addEventListener('change', toggleOverlayFields);
      toggleOverlayFields();
    }

    // State/Centre configuration (FIXED LOGIC)
    const stateSelect = panel.querySelector(`#lane${i}_state`);
    const centreSelect = panel.querySelector(`#lane${i}_centre`);
    const sceneCheckbox = document.querySelector(`.enable-checkbox[data-index="${i}"]`);

    // Track loading state to prevent conflicts
    let isLoadingCentres = false;
    let isLoadingSeries = false;

    async function loadCentres() {
      if (isLoadingCentres || !stateSelect || !centreSelect) return;
      
      isLoadingCentres = true;
      centreSelect.innerHTML = '<option value="">-- Loading centres... --</option>';
      const state = stateSelect.value;
      
      if (!state) {
        centreSelect.innerHTML = '<option value="">-- Select Centre --</option>';
        isLoadingCentres = false;
        return;
      }
      
      try {
        console.log(`Loading centres for state: ${state}`);
        const res = await fetch(`/get_centres/${state}`);
        
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        
        const centres = await res.json();
        console.log(`Received centres:`, centres);
        
        centreSelect.innerHTML = '<option value="">-- Select Centre --</option>';
        
        // Check if we have centres data
        if (centres && typeof centres === 'object' && !centres.error) {
          for (const [id, name] of Object.entries(centres)) {
            const opt = document.createElement('option');
            opt.value = id;
            opt.textContent = name;
            centreSelect.appendChild(opt);
          }
          
          // Restore saved value if it exists
          const savedCentre = centreSelect.dataset.saved;
          if (savedCentre && centreSelect.querySelector(`option[value="${savedCentre}"]`)) {
            centreSelect.value = savedCentre;
            console.log(`Restored centre: ${savedCentre} for lane ${i}`);
            
            // Only load series if centre was successfully set
            setTimeout(() => loadSeries(), 100);
          }
        } else {
          console.error('Invalid centres data:', centres);
          centreSelect.innerHTML = '<option value="">-- Error loading centres --</option>';
        }
      } catch (err) {
        console.error('Failed to load centres:', err);
        centreSelect.innerHTML = '<option value="">-- Error loading centres --</option>';
      } finally {
        isLoadingCentres = false;
      }
    }
    
    async function loadSeries() {
      if (isLoadingSeries || !centreSelect || !oddField || !evenField) return;
      
      isLoadingSeries = true;
      const centreId = centreSelect.value;
      
      if (!centreId) {
        isLoadingSeries = false;
        return;
      }
      
      const laneNameInput = panel.querySelector(`input[name="lane${i}_name"]`);
      if (!laneNameInput) {
        isLoadingSeries = false;
        return;
      }
      
      const laneName = laneNameInput.value;
      const lanes = laneName.split('&').map(x => x.trim());
      
      try {
        console.log(`Loading series for centre ${centreId}, lanes: ${lanes.join(',')}`);
        const res = await fetch(`/get_series/${centreId}?lanes=${lanes.join(',')}`);
        
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        
        const data = await res.json();
        console.log('Series data received:', data);
        
        if (data.lane1) oddField.value = data.lane1;
        if (data.lane2) evenField.value = data.lane2;
        
        if (data.warning) {
          console.warn(`Series warning: ${data.warning}`);
        }
        
        // Start polling if needed
        if (scoringDropdown && scoringDropdown.value === 'livescores' && sceneCheckbox && sceneCheckbox.checked) {
          setTimeout(() => startSeriesPolling(i), 500);
        }
      } catch (err) {
        console.error('Error loading series:', err);
      } finally {
        isLoadingSeries = false;
      }
    }

    // Event listeners for state/centre
    if (stateSelect) {
      stateSelect.addEventListener('change', () => {
        console.log(`State changed to: ${stateSelect.value} for lane ${i}`);
        loadCentres();
      });
    }
    
    if (centreSelect) {
      centreSelect.addEventListener('change', () => {
        console.log(`Centre changed to: ${centreSelect.value} for lane ${i}`);
        loadSeries();
      });
    }

    // Initialize state/centre if saved values exist
    setTimeout(() => {
      if (stateSelect && stateSelect.dataset.saved) {
        console.log(`Initializing state: ${stateSelect.dataset.saved} for lane ${i}`);
        stateSelect.value = stateSelect.dataset.saved;
        loadCentres();
      }
    }, 200);
  }

  // Stream panel navigation
  document.querySelectorAll('.stream-button').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = btn.dataset.index;
      document.querySelectorAll('.stream-panel').forEach(p => p.style.display = 'none');
      const targetPanel = document.getElementById(`panel-lane${idx}`);
      if (targetPanel) targetPanel.style.display = 'block';
      document.querySelectorAll('.stream-button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Activate first panel
  const firstButton = document.querySelector('.stream-button');
  if (firstButton) firstButton.click();

  // Enable/disable checkboxes (FIXED to prevent infinite loops)
  document.querySelectorAll('.enable-checkbox').forEach(cb => {
    cb.addEventListener('change', () => {
      if (!isSubmitting) {
        console.log(`Checkbox ${cb.dataset.index} changed, submitting form`);
        document.getElementById('config-form').submit();
      }
    });
  });
});

// Polling function for series updates
function startSeriesPolling(pair) {
  const oddField = document.querySelector(`#lane${pair}_odd_lane_src`);
  const evenField = document.querySelector(`#lane${pair}_even_lane_src`);
  const scoringDropdown = document.querySelector(`#lane${pair}_scoring_type`);

  if (!oddField || !evenField || !scoringDropdown) return;

  // Clear any existing polling for this pair
  if (window.seriesPollingIntervals && window.seriesPollingIntervals[pair]) {
    clearInterval(window.seriesPollingIntervals[pair]);
    delete window.seriesPollingIntervals[pair];
  }

  if (!window.seriesPollingIntervals) window.seriesPollingIntervals = {};

  window.seriesPollingIntervals[pair] = setInterval(() => {
    // Stop polling if not using livescores
    if (scoringDropdown.value !== 'livescores') return;

    // Check if elements still exist
    if (!document.body.contains(oddField) || !document.body.contains(evenField)) {
      clearInterval(window.seriesPollingIntervals[pair]);
      delete window.seriesPollingIntervals[pair];
      console.log(`Stopped orphaned polling for lane pair ${pair}`);
      return;
    }

    fetch(`/get-overlay-links/${pair}`)
      .then(res => res.json())
      .then(data => {
        if (data.odd && oddField.value !== data.odd) {
          oddField.value = data.odd;
        }
        if (data.even && evenField.value !== data.even) {
          evenField.value = data.even;
        }
      })
      .catch(err => console.error('Polling error:', err));
  }, 5000);
}


// Flash message fadeout
document.addEventListener('DOMContentLoaded', function () {
  const flashMessages = document.querySelectorAll('.flash');
  flashMessages.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = 'opacity 0.5s ease';
      flash.style.opacity = '0';
      setTimeout(() => flash.remove(), 500);
    }, 6000);
  });
});

(async function setupAudioDropdowns() {
  const audioSections = document.querySelectorAll('.audio-section');
  
  try {
    const response = await fetch('/get_audio_devices');
    const audioInputs = await response.json();

    audioSections.forEach(section => {
      const i = section.dataset.index;
      const container = section.querySelector(`#lane${i}_audio_dropdowns`);
      if (!container) return;

      // Get saved devices
      const saved = [];
      document.querySelectorAll(`input[name^="lane${i}_audio_streams_"]`).forEach((inp, idx) => {
        const value = inp.value?.trim();
        const nameInput = document.querySelector(`input[name="lane${i}_audio_names_${idx}"]`);
        const friendlyName = nameInput ? nameInput.value?.trim() : '';
        if (value) {
          saved.push({ label: value, friendly_name: friendlyName });
        }
      });

      function renderDropdowns(selectedList) {
        container.innerHTML = '';
        
        const usedDevices = selectedList.map(item => item?.label || '').filter(Boolean);
        const availableDevices = audioInputs.filter(dev => !usedDevices.includes(dev));
        const totalDropdowns = availableDevices.length > 0 ? selectedList.length + 1 : selectedList.length;
        const finalDropdowns = Math.max(1, totalDropdowns);
        
        for (let j = 0; j < finalDropdowns; j++) {
          const row = document.createElement('div');
          row.className = 'audio-select-row';

          const sel = document.createElement('select');
          sel.name = `lane${i}_audio_streams_${j}`;
          sel.className = 'audio-select-dropdown';

          const used = new Set(selectedList.slice(0, j).map(item => item?.label || '').filter(Boolean));
          
          sel.innerHTML = '<option value="">-- Select Device --</option>';
          
          audioInputs.forEach(dev => {
            if (!dev || typeof dev !== 'string') return;
            const opt = document.createElement('option');
            opt.value = dev;
            opt.textContent = dev;
            opt.selected = selectedList[j]?.label === dev;
            if (used.has(dev)) {
              opt.disabled = true;
              opt.textContent += ' (in use)';
            }
            sel.appendChild(opt);
          });

          const nameInput = document.createElement('input');
          nameInput.type = 'text';
          nameInput.name = `lane${i}_audio_names_${j}`;
          nameInput.className = 'audio-name-input';
          nameInput.placeholder = 'Friendly Name';
          nameInput.value = selectedList[j]?.friendly_name || '';

          const removeBtn = document.createElement('button');
          removeBtn.type = 'button';
          removeBtn.textContent = '×';
          removeBtn.className = 'remove-audio-btn';

          sel.addEventListener('change', () => {
            const updated = [];
            container.querySelectorAll('.audio-select-row').forEach(r => {
              const select = r.querySelector('select');
              const nameField = r.querySelector('input[type="text"]');
              if (select?.value) {
                updated.push({ label: select.value, friendly_name: nameField?.value || '' });
              }
            });
            renderDropdowns(updated);
          });

          removeBtn.addEventListener('click', () => {
            if (j < selectedList.length) {
              selectedList.splice(j, 1);
              renderDropdowns(selectedList);
            }
          });

          row.appendChild(sel);
          row.appendChild(nameInput);
          if (j < selectedList.length && selectedList[j]?.label) {
            row.appendChild(removeBtn);
          }
          container.appendChild(row);
        }
      }

      renderDropdowns(saved);
    });
  } catch (err) {
    console.error('Failed to fetch audio devices:', err);
  }
})();