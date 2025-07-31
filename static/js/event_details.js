document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('event-form');
    let venueInput = document.getElementById('venue');
    let venueLookupBtn = document.getElementById('venue-lookup');
    let addSquadBtn = document.getElementById('add-squad');
    let squadsContainer = document.getElementById('squads-container');
    let saveTemplateBtn = document.getElementById('save-template');
    let loadTemplateBtn = document.getElementById('load-template-btn');
    let clearFormBtn = document.getElementById('clear-form');
    let logoUpload = document.getElementById('logo_upload');
    let bannerPreview = document.getElementById('banner-preview');

    // Banner preview functionality with immediate upload
    logoUpload.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            // Show preview
            const reader = new FileReader();
            reader.onload = function(e) {
                bannerPreview.innerHTML = `<img src="${e.target.result}" alt="Banner Preview">`;
            };
            reader.readAsDataURL(file);
            
            // IMMEDIATELY upload the banner to server
            const formData = new FormData();
            formData.append('banner_file', file);
            
            fetch('/upload_banner_temp', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Store the banner URL for template saving
                    logoUpload.setAttribute('data-banner-url', data.banner_url);
                    console.log('Banner uploaded:', data.banner_url);
                } else {
                    console.error('Banner upload failed:', data.error);
                }
            })
            .catch(error => {
                console.error('Banner upload error:', error);
            });
        } else {
            bannerPreview.innerHTML = 'Banner preview will appear here';
            logoUpload.removeAttribute('data-banner-url');
        }
    });

    // Basic Venue Lookup
    venueLookupBtn.addEventListener('click', function() {
        const venue = venueInput.value || prompt('Enter venue name or address:');
        if (venue) {
            venueInput.value = venue;
            window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue)}`, '_blank');
        }
    });

    // Add Squad
    addSquadBtn.addEventListener('click', function() {
        const squadDiv = document.createElement('div');
        squadDiv.className = 'squad-item';
        squadDiv.innerHTML = `
            <input type="file" name="lane_draw_csv[]" class="form-control squad-file" accept=".csv">
            <button type="button" class="remove-squad">Remove</button>
        `;
        squadsContainer.appendChild(squadDiv);
    });

    // Remove Squad
    squadsContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-squad')) {
            e.target.parentElement.remove();
        }
    });

    // Save Template - SERVER SIDE with Banner Support
    saveTemplateBtn.addEventListener('click', function() {
        const templateName = document.getElementById('template_name').value;
        const eventName = document.getElementById('event_name').value;
        const venue = document.getElementById('venue').value;
        
        if (!templateName) {
            alert('Please enter a template name');
            return;
        }
        
        if (templateName && eventName && venue) {
            // Get the actual uploaded banner URL
            const logoUpload = document.getElementById('logo_upload');
            const bannerUrl = logoUpload.getAttribute('data-banner-url');
            const hasBanner = !!bannerUrl;
            
            fetch('/save_venue_template', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    template_name: templateName,
                    event_name: eventName,
                    venue: venue,
                    has_banner: hasBanner,
                    banner_url: bannerUrl
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Template saved successfully!');
                    document.getElementById('template_name').value = '';
                    updateTemplateDropdown();
                } else {
                    alert('Error saving template: ' + data.error);
                }
            })
            .catch(error => {
                alert('Error saving template: ' + error);
            });
        } else {
            alert('Please fill in template name, event name, and venue before saving.');
        }
    });

    // Load Template - SERVER SIDE with Auto-Activation
    loadTemplateBtn.addEventListener('click', function() {
        const templateName = document.getElementById('load-template').value;
        if (!templateName) {
            alert('Please select a template to load');
            return;
        }
        
        fetch('/get_venue_templates')
            .then(response => response.json())
            .then(templates => {
                const template = templates.find(t => t.name === templateName);
                if (template) {
                    // Load basic fields
                    document.getElementById('event_name').value = template.event_name;
                    document.getElementById('venue').value = template.venue;
                    
                    // Load banner if it exists
                    const bannerPreview = document.getElementById('banner-preview');
                    const logoUpload = document.getElementById('logo_upload');
                    
                    if (template.banner_url) {
                        // Show the banner in preview
                        bannerPreview.innerHTML = `<img src="${template.banner_url}" alt="Template Banner">`;
                        // Store the banner URL for saving
                        logoUpload.setAttribute('data-banner-url', template.banner_url);
                    } else {
                        // Clear banner preview
                        bannerPreview.innerHTML = 'Banner preview will appear here';
                        logoUpload.removeAttribute('data-banner-url');
                        logoUpload.value = ''; // Clear file input
                    }
                    
alert('Template loaded successfully!');
                    
                } else {
                    alert('Template not found');
                }
            })
            .catch(error => {
                alert('Error loading template: ' + error);
            });
    });

    // Clear Form
    if (clearFormBtn) {
        clearFormBtn.addEventListener('click', function() {
            if (confirm('Clear all form data?')) {
                form.reset();
                bannerPreview.innerHTML = 'Banner preview will appear here';
                squadsContainer.innerHTML = '';
                localStorage.removeItem('eventFormDraft');
            }
        });
    }

    // Update Template Dropdown - SERVER SIDE
    function updateTemplateDropdown() {
        fetch('/get_venue_templates')
            .then(response => response.json())
            .then(templates => {
                const select = document.getElementById('load-template');
                select.innerHTML = '<option value="">Select Template</option>';
                templates.forEach(template => {
                    const option = document.createElement('option');
                    option.value = template.name;
                    option.textContent = template.name;
                    select.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error loading templates:', error);
            });
    }

// Load current event data into form on page load
function loadCurrentEventIntoForm() {
   // Check if there's current event data passed from the server
   const currentEventElement = document.querySelector('[data-current-event]');
   if (currentEventElement) {
       try {
           const currentEvent = JSON.parse(currentEventElement.getAttribute('data-current-event'));
           
           // Populate form fields
           if (currentEvent.event_name) {
               document.getElementById('event_name').value = currentEvent.event_name;
           }
           if (currentEvent.venue) {
               document.getElementById('venue').value = currentEvent.venue;
           }
           if (currentEvent.event_dates_start) {
               document.getElementById('event_dates_start').value = currentEvent.event_dates_start;
           }
           if (currentEvent.event_dates_end) {
               document.getElementById('event_dates_end').value = currentEvent.event_dates_end;
           }
           
           // Set banner data attribute for OBS (don't touch the preview - template handles it)
           if (currentEvent.banner_url) {
               const logoUpload = document.getElementById('logo_upload');
               logoUpload.setAttribute('data-banner-url', currentEvent.banner_url);
           }
           
       } catch (e) {
           console.error('Error loading current event data:', e);
       }
   }
}

// Call it after initialization
loadCurrentEventIntoForm();
    
    // Initialize template dropdown
    updateTemplateDropdown();

    // Form submission handler
    form.addEventListener('submit', function(e) {
                // Inject banner URL into hidden field before form is sent
        const logoUpload = document.getElementById('logo_upload');
        const bannerUrl = logoUpload.getAttribute('data-banner-url');
        if (bannerUrl) {
            const hiddenField = document.getElementById('hidden_banner_url');
            if (hiddenField) hiddenField.value = bannerUrl;
        }
        const eventName = document.getElementById('event_name').value.trim();
        const eventDatesStart = document.getElementById('event_dates_start').value;
        const eventDatesEnd = document.getElementById('event_dates_end').value;
        const venue = document.getElementById('venue').value.trim();

        // Basic validation
        if (!eventName || !eventDatesStart || !eventDatesEnd || !venue) {
            e.preventDefault();
            alert('Please fill in all required fields (Event Name, Dates, and Venue).');
            return;
        }

        // Date validation
        if (new Date(eventDatesStart) >= new Date(eventDatesEnd)) {
            e.preventDefault();
            alert('Start date must be before the end date.');
            return;
        }

        // Lane draw is now optional - no validation needed
        
        // Show loading state
        const submitBtn = e.target.querySelector('.btn-primary');
        if (submitBtn) {
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Activating Event...';
            
            // Reset button after timeout (in case of error)
            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }, 5000);
        }
    });

    // Auto-save to localStorage on form changes (optional)
    const formInputs = form.querySelectorAll('input[type="text"], input[type="date"]');
    formInputs.forEach(input => {
        input.addEventListener('change', function() {
            const formData = {};
            formInputs.forEach(inp => {
                if (inp.value) formData[inp.name] = inp.value;
            });
            localStorage.setItem('eventFormDraft', JSON.stringify(formData));
        });
    });

    // Restore draft on page load
    const draft = localStorage.getItem('eventFormDraft');
    if (draft) {
        try {
            const formData = JSON.parse(draft);
            Object.keys(formData).forEach(key => {
                const input = form.querySelector(`[name="${key}"]`);
                if (input && input.type !== 'file') {
                    input.value = formData[key];
                }
            });
        } catch (e) {
            // Ignore invalid draft data
        }
    }

    // Clear draft on successful submission
    form.addEventListener('submit', function() {
        localStorage.removeItem('eventFormDraft');
    });
});

// Auto-hide flash messages after 5 seconds
const flashMessages = document.querySelectorAll('.alert');
flashMessages.forEach(function(message) {
    setTimeout(function() {
        message.style.transition = 'opacity 0.5s ease-out';
        message.style.opacity = '0';
        setTimeout(function() {
            message.remove();
        }, 500);
    }, 5000);
});

// Add close button functionality
const closeButtons = document.querySelectorAll('.alert .close, .alert .btn-close');
closeButtons.forEach(function(button) {
    button.addEventListener('click', function() {
        const alert = this.closest('.alert');
        alert.style.transition = 'opacity 0.3s ease-out';
        alert.style.opacity = '0';
        setTimeout(function() {
            alert.remove();
        }, 300);
    });
});