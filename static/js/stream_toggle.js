document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing stream toggle button');
  const streamButton = document.getElementById('stream-button');
  if (!streamButton) {
    console.error('Stream button missing');
    return;
  }

  async function updateStreamButtonState(retries = 3, delay = 1000) {
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetch('/stream_status');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (data.error) throw new Error(data.error);
        streamButton.textContent = data.streaming ? 'NOW\nSTREAMING' : 'NOT\nSTREAMING';
        if (data.streaming) {
          streamButton.classList.remove('not-streaming');
          streamButton.classList.add('streaming');
        } else {
          streamButton.classList.remove('streaming');
          streamButton.classList.add('not-streaming');
        }
        console.log('Stream status updated:', data);
        return;
      } catch (err) {
        console.warn(`Stream status fetch attempt ${i+1} failed: ${err.message}`);
        if (i < retries - 1) await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    console.error('Failed to fetch streaming status after retries');
  }

  // Initial state update
  updateStreamButtonState();

  // Periodic polling for state sync
  setInterval(updateStreamButtonState, 5000);

  // Toggle stream on click
  streamButton.addEventListener('click', async (e) => {
    e.preventDefault();
    console.log('Stream button clicked');
    try {
      const response = await fetch('/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      console.log('Stream toggle response status:', response.status);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      console.log('Stream toggle response data:', data);
      if (data.error) {
        console.error('Stream toggle error:', data.error);
      } else {
        streamButton.textContent = data.streaming ? 'NOW\nSTREAMING' : 'NOT\nSTREAMING';
        if (data.streaming) {
          streamButton.classList.remove('not-streaming');
          streamButton.classList.add('streaming');
        } else {
          streamButton.classList.remove('streaming');
          streamButton.classList.add('not-streaming');
        }
        console.log('Toggle stream successful:', data);
      }
    } catch (err) {
      console.error('Error toggling stream:', err.message);
    }
  });
});