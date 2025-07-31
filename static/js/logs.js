// System Logs JavaScript

// Only initialize logs functionality if we're actually on the logs page
if (window.location.pathname === '/logs') {
    
    // Tab switching
    document.addEventListener('DOMContentLoaded', function() {
        const logTabs = document.querySelectorAll('.logs-tabs .log-tab');
        const logContents = document.querySelectorAll('.tab-content');
        
        logTabs.forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Remove active from all tabs
                logTabs.forEach(t => t.classList.remove('active'));
                logContents.forEach(c => c.classList.remove('active'));
                
                // Add active to clicked tab
                this.classList.add('active');
                
                // Show corresponding content
                const tabName = this.getAttribute('data-tab');
                const content = document.getElementById(tabName + '-content');
                if (content) {
                    content.classList.add('active');
                }
            });
        });
        
        // Auto-scroll to bottom on load
        const containers = document.querySelectorAll('.log-container');
        containers.forEach(container => {
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        });
    });
}

// Global functions that can be called from onclick handlers
window.scrollToBottom = function(tabName) {
    const container = document.getElementById(tabName + '-log');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

window.clearLog = function(category) {
    if (confirm('Are you sure you want to clear this log?')) {
        fetch(`/logs/clear/${category}`, {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            })
            .catch(error => {
                console.error('Error clearing log:', error);
            });
    }
}

window.downloadLog = function(tabName) {
    const container = document.getElementById(tabName + '-log');
    if (!container) return;
    
    const text = container.textContent;
    const blob = new Blob([text], {type: 'text/plain'});
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cornerpins_${tabName}_log_${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}