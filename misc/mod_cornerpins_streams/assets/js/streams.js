function loadStreams(apiUrl) {
    console.log("Attempting to load streams from: " + apiUrl);
    jQuery.ajax({
        url: apiUrl,
        method: 'GET',
        headers: { 'ngrok-skip-browser-warning': '1' },
        success: function(data) {
            console.log("Received data: ", data);
            
            const streams = data.streams || data; // Support both old and new format
            const bannerUrl = data.banner_url;
            const hasBanner = data.has_banner;

            console.log("Banner check - hasBanner:", hasBanner, "bannerUrl:", bannerUrl);
            console.log("About to check banner condition:", hasBanner, "&&", bannerUrl);

            const tiles = jQuery('#stream-tiles').empty();

            // Remove existing banner if present
            jQuery('.event-banner').remove();

            // Add banner at top if available
            if (hasBanner && bannerUrl) {
                const apiUrlObj = new URL(apiUrl);
                const ngrokBase = `${apiUrlObj.protocol}//${apiUrlObj.host}`;
                const fullBannerUrl = bannerUrl.startsWith('http') ? bannerUrl : ngrokBase + bannerUrl;

                console.log("Resolved banner URL:", fullBannerUrl);
                console.log("Attempting to fetch banner:", fullBannerUrl);

                // Fetch banner with ngrok header
                fetch(fullBannerUrl, {
                    headers: { 'ngrok-skip-browser-warning': '1' },
                    mode: 'cors',
                    credentials: 'omit'
                })
                .then(response => {
                    console.log("Banner fetch response:", response.status, response.statusText);
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return response.blob();
                })
                .then(blob => {
                    console.log("Banner blob received, size:", blob.size);
                    if (blob.size === 0) {
                        throw new Error("Empty blob received");
                    }
                    const imageUrl = URL.createObjectURL(blob);
                    const $bannerImg = jQuery('<img>', {
                        src: imageUrl,
                        alt: 'Event Banner',
                        crossOrigin: 'anonymous'
                    }).on('load', function() {
                        console.log("Banner image rendered successfully");
                    }).on('error', function() {
                        console.error("Banner image failed to render");
                    });
                    
                    const $bannerDiv = jQuery('<div class="event-banner"></div>').append($bannerImg);
                    jQuery('#stream-tiles').before($bannerDiv);
                })
                .catch(error => {
                    console.error('Banner fetch failed:', error);
                    console.error('Error details:', error.message);
                });
            }

            if (!streams.length) {
                tiles.append('<p>No enabled lanes.</p>');
                return;
            }

            streams.forEach(stream => {
                const streamingImage = stream.streaming
                    ? '/modules/mod_cornerpins_streams/assets/images/now_streaming_small.png'
                    : '/modules/mod_cornerpins_streams/assets/images/streaming_shortly_small.png';

                tiles.append(`
                    <div class="stream-tile" data-stream-url="${stream.embed_url}">
                        <h3>${stream.name}</h3>
                        <img class="stream-image" src="${streamingImage}">
                        <p class="stream-status">${stream.statusText || ''}</p>
                    </div>
                `);
            });

            const statusUrl = apiUrl.replace('/api/streams', '/stream_status');
            updateStreamStatus(statusUrl);
            setupTileClick();

            setInterval(() => {
                updateStreamStatus(statusUrl);
            }, 15000);
        },
        error: function(xhr) {
            console.log("API Error: ", xhr.status, xhr.responseText);
        }
    });
}

function updateStreamStatus(statusUrl) {
    jQuery.ajax({
        url: statusUrl,
        method: 'GET',
        headers: { 'ngrok-skip-browser-warning': '1' },
        success: function(data) {
            jQuery('.stream-tile').each(function() {
                const $tile = jQuery(this);
                const tileUrl = $tile.data('stream-url');

                if (jQuery('#stream-modal').is(':visible')) {
                    const currentUrl = jQuery('#stream-modal iframe').attr('src');
                    if (currentUrl && currentUrl.includes(tileUrl)) {
                        return;
                    }
                }

                const isStreaming = data.streaming;
                const newImage = isStreaming
                    ? '/modules/mod_cornerpins_streams/assets/images/now_streaming_small.png'
                    : '/modules/mod_cornerpins_streams/assets/images/streaming_shortly_small.png';

                $tile.find('.stream-image').attr('src', newImage);
                $tile.data('streaming', isStreaming);
            });
        },
        error: function() {
            jQuery('.stream-image').attr('src', '/modules/mod_cornerpins_streams/assets/images/streaming_shortly_small.png');
        }
    });
}

function setupTileClick() {
    jQuery('.stream-tile').off('click').on('click', function() {
        const $tile = jQuery(this);
        if ($tile.data('streaming')) {
            let $modal = jQuery('#stream-modal');

            if ($modal.length === 0) {
                $modal = jQuery(`
                    <div id="stream-modal">
                        <div class="modal-content">
                            <iframe frameborder="0" allow="fullscreen"></iframe>
                            <button class="close-btn">Close</button>
                            <button class="fullscreen-btn">Fullscreen</button>
                        </div>
                    </div>
                `);

                $modal.css({
                    display: 'none',
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    background: 'rgba(0,0,0,0.8)',
                    zIndex: 1000
                });

                $modal.find('.modal-content').css({
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: '50%',
                    height: 'auto',
                    aspectRatio: '16/9',
                    background: '#000'
                });

                $modal.find('.close-btn').on('click', function() {
                    $modal.hide();
                    $modal.find('iframe').attr('src', '');
                });

                $modal.find('.fullscreen-btn').on('click', function() {
                    const $content = $modal.find('.modal-content');
                    const isHalfSize = $content.width() === jQuery(window).width() * 0.5;

                    if (isHalfSize) {
                        $content.css({ width: '100%', height: 'auto' });
                    } else {
                        $content.css({ width: '50%', height: 'auto' });
                    }
                });

                jQuery('body').append($modal);
            }

            let streamUrl = $tile.data('stream-url');
            if (streamUrl.includes('youtube.com/embed')) {
                streamUrl += (streamUrl.includes('?') ? '&' : '?') + 'rel=0&modestbranding=1&showinfo=0';
            }

            $modal.find('iframe').attr('src', streamUrl);
            $modal.show();
        }
    });
}