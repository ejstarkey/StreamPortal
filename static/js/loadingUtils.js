// /static/js/loadingUtils.js
// Universal loading system for CornerPins Flask application

class LoadingManager {
    constructor() {
        this.activeLoaders = new Set();
        this.createGlobalLoader();
    }

    createGlobalLoader() {
        // Create global loading overlay
        const overlay = document.createElement('div');
        overlay.id = 'global-loading-overlay';
        overlay.className = 'loading-overlay';
        overlay.style.display = 'none';
        
        overlay.innerHTML = `
            <div class="loading-content">
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
                    <div class="loading-text" id="loading-message">Processing...</div>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        this.overlay = overlay;
        this.messageElement = overlay.querySelector('#loading-message');
    }

    show(message = 'Processing...', containerId = null) {
        const loaderId = this.generateId();
        this.activeLoaders.add(loaderId);
        
        if (containerId) {
            this.showInContainer(containerId, message, loaderId);
        } else {
            this.showGlobal(message);
        }
        
        return loaderId;
    }

    showGlobal(message) {
        this.messageElement.textContent = message;
        this.overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    showInContainer(containerId, message, loaderId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`Container ${containerId} not found, falling back to global loader`);
            this.showGlobal(message);
            return;
        }

        const existingLoader = container.querySelector('.inline-loading');
        if (existingLoader) {
            existingLoader.remove();
        }

        const inlineLoader = document.createElement('div');
        inlineLoader.className = 'inline-loading';
        inlineLoader.setAttribute('data-loader-id', loaderId);
        inlineLoader.innerHTML = `
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

        container.style.position = 'relative';
        container.appendChild(inlineLoader);
    }

    hide(loaderId = null) {
        if (loaderId) {
            this.activeLoaders.delete(loaderId);
            
            // Remove inline loader with specific ID
            const inlineLoader = document.querySelector(`[data-loader-id="${loaderId}"]`);
            if (inlineLoader) {
                inlineLoader.remove();
                return;
            }
        }

        // If no active loaders or hiding global
        if (this.activeLoaders.size === 0 || !loaderId) {
            this.overlay.style.display = 'none';
            document.body.style.overflow = '';
            this.activeLoaders.clear();
        }
    }

    updateMessage(message, loaderId = null) {
        if (loaderId) {
            const inlineLoader = document.querySelector(`[data-loader-id="${loaderId}"] .loading-text`);
            if (inlineLoader) {
                inlineLoader.textContent = message;
                return;
            }
        }
        
        this.messageElement.textContent = message;
    }

    generateId() {
        return 'loader_' + Math.random().toString(36).substr(2, 9);
    }
}

// Initialize global loading manager
const loadingManager = new LoadingManager();

// Simple utility functions - MANUAL USE ONLY
window.showLoading = (message, containerId) => loadingManager.show(message, containerId);
window.hideLoading = (loaderId) => loadingManager.hide(loaderId);
window.updateLoadingMessage = (message, loaderId) => loadingManager.updateMessage(message, loaderId);