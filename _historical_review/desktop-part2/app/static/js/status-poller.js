/**
 * Empire v7.3 - Status Polling Utility
 * Task 11.4: Frontend polling logic helper functions
 *
 * Provides unified status polling with WebSocket fallback support.
 *
 * Features:
 * - Exponential backoff for failed requests
 * - Automatic retry on network errors
 * - Seamless WebSocket/REST switching
 * - Progress tracking and callbacks
 * - Memory leak prevention
 */

(function (global) {
    'use strict';

    /**
     * Configuration constants
     */
    const DEFAULT_CONFIG = {
        baseUrl: '/api/status',
        wsBaseUrl: 'ws://localhost:8000/ws',
        defaultPollInterval: 2000,
        maxPollInterval: 30000,
        minPollInterval: 1000,
        maxRetries: 5,
        backoffMultiplier: 1.5,
        timeout: 10000,
        preferWebSocket: true
    };

    /**
     * Status values that indicate completion
     */
    const TERMINAL_STATUSES = [
        'success',
        'completed',
        'failure',
        'failed',
        'cancelled'
    ];

    /**
     * StatusPoller class
     * Handles polling for resource status with automatic backoff and WebSocket fallback
     */
    class StatusPoller {
        /**
         * Create a new StatusPoller
         * @param {Object} config - Configuration options
         */
        constructor(config = {}) {
            this.config = { ...DEFAULT_CONFIG, ...config };
            this.activePollers = new Map();
            this.websockets = new Map();
        }

        /**
         * Start polling for a resource's status
         * @param {string} resourceId - ID of the resource to poll
         * @param {string} resourceType - Type: 'task', 'document', 'batch'
         * @param {Object} callbacks - Event callbacks
         * @param {Function} callbacks.onStatus - Called with each status update
         * @param {Function} callbacks.onProgress - Called with progress updates
         * @param {Function} callbacks.onComplete - Called when processing completes
         * @param {Function} callbacks.onError - Called on errors
         * @returns {string} Poller ID for cancellation
         */
        startPolling(resourceId, resourceType, callbacks = {}) {
            const pollerId = `${resourceType}-${resourceId}-${Date.now()}`;

            const pollerState = {
                resourceId,
                resourceType,
                callbacks,
                pollInterval: this.config.defaultPollInterval,
                retryCount: 0,
                timerId: null,
                isActive: true,
                useWebSocket: false
            };

            this.activePollers.set(pollerId, pollerState);

            // Try WebSocket first if preferred
            if (this.config.preferWebSocket) {
                this._tryWebSocket(pollerId, pollerState);
            } else {
                this._schedulePoll(pollerId, pollerState);
            }

            return pollerId;
        }

        /**
         * Stop polling for a resource
         * @param {string} pollerId - ID returned from startPolling
         */
        stopPolling(pollerId) {
            const state = this.activePollers.get(pollerId);

            if (state) {
                state.isActive = false;

                // Clear any pending poll
                if (state.timerId) {
                    clearTimeout(state.timerId);
                    state.timerId = null;
                }

                // Close WebSocket if active
                if (state.useWebSocket) {
                    this._closeWebSocket(state.resourceType, state.resourceId);
                }

                this.activePollers.delete(pollerId);
            }
        }

        /**
         * Stop all active polling
         */
        stopAll() {
            for (const [pollerId] of this.activePollers) {
                this.stopPolling(pollerId);
            }
        }

        /**
         * Poll once for status (no subscription)
         * @param {string} resourceId - ID of the resource
         * @param {string} resourceType - Type: 'task', 'document', 'batch'
         * @returns {Promise<Object>} Status response
         */
        async pollOnce(resourceId, resourceType) {
            const endpoint = this._getEndpoint(resourceType, resourceId);
            return this._fetchStatus(endpoint);
        }

        /**
         * Batch poll for multiple resources
         * @param {Array<string>} resourceIds - Array of resource IDs
         * @param {string} resourceType - Type of all resources
         * @returns {Promise<Object>} Batch status response
         */
        async batchPoll(resourceIds, resourceType) {
            const url = `${this.config.baseUrl}/batch-check`;
            const params = new URLSearchParams();
            resourceIds.forEach(id => params.append('resource_ids', id));
            params.append('resource_type', resourceType);

            const response = await fetch(`${url}?${params.toString()}`, {
                method: 'POST',
                headers: this._getHeaders()
            });

            if (!response.ok) {
                throw new Error(`Batch poll failed: ${response.status}`);
            }

            return response.json();
        }

        // =====================================================================
        // Private Methods
        // =====================================================================

        /**
         * Try to establish WebSocket connection
         */
        _tryWebSocket(pollerId, state) {
            const wsUrl = this._getWebSocketUrl(state.resourceType, state.resourceId);

            try {
                const ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    console.log(`[StatusPoller] WebSocket connected for ${state.resourceType}/${state.resourceId}`);
                    state.useWebSocket = true;
                    this.websockets.set(`${state.resourceType}-${state.resourceId}`, ws);
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this._handleStatusUpdate(pollerId, state, data);
                    } catch (e) {
                        console.error('[StatusPoller] Failed to parse WebSocket message:', e);
                    }
                };

                ws.onerror = (error) => {
                    console.warn('[StatusPoller] WebSocket error, falling back to REST:', error);
                    state.useWebSocket = false;
                    this._schedulePoll(pollerId, state);
                };

                ws.onclose = () => {
                    console.log(`[StatusPoller] WebSocket closed for ${state.resourceType}/${state.resourceId}`);
                    if (state.isActive && !state.useWebSocket) {
                        // Already fell back to REST
                    } else if (state.isActive) {
                        // Unexpected close, fall back to REST
                        state.useWebSocket = false;
                        this._schedulePoll(pollerId, state);
                    }
                };

                // Set timeout for connection
                setTimeout(() => {
                    if (ws.readyState === WebSocket.CONNECTING) {
                        console.warn('[StatusPoller] WebSocket connection timeout, falling back to REST');
                        ws.close();
                        state.useWebSocket = false;
                        this._schedulePoll(pollerId, state);
                    }
                }, 5000);

            } catch (error) {
                console.warn('[StatusPoller] WebSocket not available, using REST:', error);
                state.useWebSocket = false;
                this._schedulePoll(pollerId, state);
            }
        }

        /**
         * Schedule next poll
         */
        _schedulePoll(pollerId, state) {
            if (!state.isActive) return;

            state.timerId = setTimeout(
                () => this._executePoll(pollerId, state),
                state.pollInterval
            );
        }

        /**
         * Execute a poll request
         */
        async _executePoll(pollerId, state) {
            if (!state.isActive) return;

            try {
                const endpoint = this._getEndpoint(state.resourceType, state.resourceId);
                const response = await this._fetchStatus(endpoint);

                // Reset retry count on success
                state.retryCount = 0;

                // Handle the status update
                this._handleStatusUpdate(pollerId, state, response);

                // Update poll interval based on server recommendation
                if (response.poll_interval_ms) {
                    state.pollInterval = Math.max(
                        this.config.minPollInterval,
                        Math.min(response.poll_interval_ms, this.config.maxPollInterval)
                    );
                }

                // Schedule next poll if still needed
                if (response.should_continue_polling && state.isActive) {
                    this._schedulePoll(pollerId, state);
                } else if (!response.should_continue_polling) {
                    // Clean up - polling complete
                    this.stopPolling(pollerId);
                }

            } catch (error) {
                this._handleError(pollerId, state, error);
            }
        }

        /**
         * Handle status update from poll or WebSocket
         */
        _handleStatusUpdate(pollerId, state, data) {
            const { callbacks } = state;

            // Call onStatus callback
            if (callbacks.onStatus) {
                callbacks.onStatus(data);
            }

            // Call onProgress if progress data available
            if (data.progress && callbacks.onProgress) {
                callbacks.onProgress(data.progress);
            }

            // Check for completion
            if (TERMINAL_STATUSES.includes(data.status?.toLowerCase())) {
                if (callbacks.onComplete) {
                    callbacks.onComplete(data);
                }

                // Stop polling on completion
                this.stopPolling(pollerId);
            }
        }

        /**
         * Handle poll error with backoff
         */
        _handleError(pollerId, state, error) {
            state.retryCount++;

            console.error(
                `[StatusPoller] Poll error (attempt ${state.retryCount}/${this.config.maxRetries}):`,
                error
            );

            // Call error callback
            if (state.callbacks.onError) {
                state.callbacks.onError(error, state.retryCount);
            }

            // Check max retries
            if (state.retryCount >= this.config.maxRetries) {
                console.error('[StatusPoller] Max retries reached, stopping');
                if (state.callbacks.onError) {
                    state.callbacks.onError(new Error('Max retries reached'), state.retryCount);
                }
                this.stopPolling(pollerId);
                return;
            }

            // Apply exponential backoff
            state.pollInterval = Math.min(
                state.pollInterval * this.config.backoffMultiplier,
                this.config.maxPollInterval
            );

            // Schedule retry
            if (state.isActive) {
                this._schedulePoll(pollerId, state);
            }
        }

        /**
         * Fetch status from REST endpoint
         */
        async _fetchStatus(endpoint) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

            try {
                const response = await fetch(endpoint, {
                    method: 'GET',
                    headers: this._getHeaders(),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                return response.json();

            } catch (error) {
                clearTimeout(timeoutId);
                throw error;
            }
        }

        /**
         * Get REST endpoint URL for resource
         */
        _getEndpoint(resourceType, resourceId) {
            const typeMap = {
                'task': 'task',
                'document': 'document',
                'batch': 'batch',
                'batch_operation': 'batch'
            };

            const path = typeMap[resourceType] || resourceType;
            return `${this.config.baseUrl}/${path}/${resourceId}`;
        }

        /**
         * Get WebSocket URL for resource
         */
        _getWebSocketUrl(resourceType, resourceId) {
            const typeMap = {
                'task': 'query',  // Tasks use query WebSocket
                'document': 'document',
                'batch': 'notifications'
            };

            const path = typeMap[resourceType] || 'notifications';

            if (path === 'notifications') {
                return `${this.config.wsBaseUrl}/notifications`;
            }

            return `${this.config.wsBaseUrl}/${path}/${resourceId}`;
        }

        /**
         * Get request headers
         */
        _getHeaders() {
            const headers = {
                'Content-Type': 'application/json'
            };

            // Add auth token if available
            const token = this._getAuthToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            return headers;
        }

        /**
         * Get auth token from storage
         */
        _getAuthToken() {
            // Check for Clerk token
            if (typeof window !== 'undefined' && window.Clerk) {
                return window.Clerk.session?.getToken();
            }

            // Check localStorage fallback
            return localStorage.getItem('auth_token');
        }

        /**
         * Close WebSocket connection
         */
        _closeWebSocket(resourceType, resourceId) {
            const key = `${resourceType}-${resourceId}`;
            const ws = this.websockets.get(key);

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }

            this.websockets.delete(key);
        }
    }

    // =========================================================================
    // Helper Functions
    // =========================================================================

    /**
     * Create a progress bar element
     * @param {Object} progress - Progress data from status response
     * @returns {HTMLElement} Progress bar element
     */
    function createProgressBar(progress) {
        const container = document.createElement('div');
        container.className = 'status-progress-container';

        const bar = document.createElement('div');
        bar.className = 'status-progress-bar';

        const fill = document.createElement('div');
        fill.className = 'status-progress-fill';
        fill.style.width = `${progress.percentage || 0}%`;

        const text = document.createElement('span');
        text.className = 'status-progress-text';
        text.textContent = progress.message || `${Math.round(progress.percentage || 0)}%`;

        bar.appendChild(fill);
        container.appendChild(bar);
        container.appendChild(text);

        return container;
    }

    /**
     * Format status for display
     * @param {Object} statusData - Status response data
     * @returns {Object} Formatted status with icon and color
     */
    function formatStatus(statusData) {
        const statusStyles = {
            'pending': { icon: '⏳', color: '#6b7280', label: 'Pending' },
            'queued': { icon: '📋', color: '#6b7280', label: 'Queued' },
            'processing': { icon: '🔄', color: '#3b82f6', label: 'Processing' },
            'started': { icon: '🔄', color: '#3b82f6', label: 'Started' },
            'success': { icon: '✅', color: '#10b981', label: 'Success' },
            'completed': { icon: '✅', color: '#10b981', label: 'Completed' },
            'failure': { icon: '❌', color: '#ef4444', label: 'Failed' },
            'failed': { icon: '❌', color: '#ef4444', label: 'Failed' },
            'cancelled': { icon: '🚫', color: '#f59e0b', label: 'Cancelled' },
            'unknown': { icon: '❓', color: '#9ca3af', label: 'Unknown' }
        };

        const status = statusData.status?.toLowerCase() || 'unknown';
        const style = statusStyles[status] || statusStyles['unknown'];

        return {
            ...style,
            raw: status,
            message: statusData.status_message || style.label
        };
    }

    /**
     * Wait for status to reach terminal state
     * @param {StatusPoller} poller - StatusPoller instance
     * @param {string} resourceId - Resource ID
     * @param {string} resourceType - Resource type
     * @param {number} timeout - Timeout in milliseconds
     * @returns {Promise<Object>} Final status
     */
    function waitForCompletion(poller, resourceId, resourceType, timeout = 300000) {
        return new Promise((resolve, reject) => {
            let timeoutId;

            const pollerId = poller.startPolling(resourceId, resourceType, {
                onComplete: (data) => {
                    clearTimeout(timeoutId);
                    resolve(data);
                },
                onError: (error, retryCount) => {
                    if (retryCount >= poller.config.maxRetries) {
                        clearTimeout(timeoutId);
                        reject(error);
                    }
                }
            });

            timeoutId = setTimeout(() => {
                poller.stopPolling(pollerId);
                reject(new Error('Polling timeout exceeded'));
            }, timeout);
        });
    }

    // =========================================================================
    // Export
    // =========================================================================

    // Create default instance
    const defaultPoller = new StatusPoller();

    // Export for different module systems
    const exports = {
        StatusPoller,
        createProgressBar,
        formatStatus,
        waitForCompletion,
        defaultPoller,
        TERMINAL_STATUSES,
        DEFAULT_CONFIG
    };

    // CommonJS
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = exports;
    }

    // AMD
    if (typeof define === 'function' && define.amd) {
        define(function () { return exports; });
    }

    // Global
    if (typeof global !== 'undefined') {
        global.EmpireStatus = exports;
    }

})(typeof window !== 'undefined' ? window : this);
