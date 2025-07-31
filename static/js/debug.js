window.addEventListener('load', () => {
    console.log('Nexus available:', typeof Nexus !== 'undefined');
    console.log('io available:', typeof io !== 'undefined');
    if (typeof Nexus === 'undefined') {
        console.error('NexusUI failed to load');
    }
    if (typeof io === 'undefined') {
        console.error('Socket.IO failed to load');
    }
});