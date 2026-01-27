/**
 * EEG Stimulus Platform - Event Logger Module
 * 
 * Handles precise timing of all experimental events.
 * Structured for easy integration with EEG systems.
 * 
 * Integration Points:
 * - Lab Streaming Layer (LSL)
 * - WebSocket bridges
 * - Parallel port triggers
 * - Serial port triggers
 */

import { Config } from './config.js';

class EventLoggerClass {
    constructor() {
        this.entries = [];
        this.experimentStartTime = null;
        this.listeners = [];
        
        // External connections (set these up before experiment)
        this.lslOutlet = null;
        this.webSocket = null;
        this.parallelPort = null;
    }
    
    /**
     * Initialize logger at experiment start
     */
    init() {
        this.entries = [];
        this.experimentStartTime = performance.now();
        this.log('EXPERIMENT_START', { 
            timestamp: Date.now(),
            isoTime: new Date().toISOString()
        });
    }
    
    /**
     * Log an event with precise timing
     * 
     * @param {string} eventType - Event type identifier
     * @param {object} data - Additional event data
     * @returns {object} The logged entry
     */
    log(eventType, data = {}) {
        const absoluteTime = performance.now();
        const relativeTime = this.experimentStartTime 
            ? absoluteTime - this.experimentStartTime 
            : 0;
        
        const entry = {
            eventType,
            absoluteTime,
            relativeTime,
            numericCode: this.getNumericCode(eventType, data),
            ...data
        };
        
        this.entries.push(entry);
        
        // Console output (can be captured by external logging)
        console.log(`[EEG_EVENT] ${eventType}`, {
            absoluteMs: absoluteTime.toFixed(3),
            relativeMs: relativeTime.toFixed(3),
            code: entry.numericCode,
            ...data
        });
        
        // Notify listeners
        this.notifyListeners(entry);
        
        // Send to external systems
        this.sendToExternalSystems(entry);
        
        return entry;
    }
    
    /**
     * Log stimulus onset
     */
    logOnset(stimulusType, stimulusCode, trialNumber) {
        return this.log('STIM_ONSET', {
            stimulusType,
            stimulusCode,
            trialNumber
        });
    }
    
    /**
     * Log stimulus offset
     */
    logOffset(stimulusType, stimulusCode, trialNumber, duration) {
        return this.log('STIM_OFFSET', {
            stimulusType,
            stimulusCode,
            trialNumber,
            actualDurationMs: duration.toFixed(3)
        });
    }
    
    /**
     * Get numeric code for EEG markers
     */
    getNumericCode(eventType, data) {
        // Base event code
        let code = Config.eventCodes[eventType] || 0;
        
        // Add stimulus-specific code if present
        if (data.stimulusCode && Config.eventCodes[data.stimulusCode]) {
            code = Config.eventCodes[data.stimulusCode];
        }
        
        return code;
    }
    
    /**
     * Add an event listener
     */
    addListener(callback) {
        this.listeners.push(callback);
    }
    
    /**
     * Remove an event listener
     */
    removeListener(callback) {
        const index = this.listeners.indexOf(callback);
        if (index > -1) {
            this.listeners.splice(index, 1);
        }
    }
    
    /**
     * Notify all listeners
     */
    notifyListeners(entry) {
        this.listeners.forEach(callback => {
            try {
                callback(entry);
            } catch (e) {
                console.error('Event listener error:', e);
            }
        });
    }
    
    // ============================================================
    // EXTERNAL SYSTEM INTEGRATION
    // ============================================================
    
    /**
     * Send event to all configured external systems
     */
    sendToExternalSystems(entry) {
        this.sendToLSL(entry);
        this.sendToWebSocket(entry);
        this.sendToParallelPort(entry);
    }
    
    /**
     * Lab Streaming Layer integration
     * Requires LSL WebSocket bridge running locally
     * 
     * Setup: npm install lsl-bridge (or similar)
     */
    sendToLSL(entry) {
        if (!this.lslOutlet) return;
        
        try {
            // Push marker with timestamp
            this.lslOutlet.push_sample([
                entry.numericCode,
                entry.absoluteTime
            ]);
        } catch (e) {
            console.warn('LSL send failed:', e);
        }
    }
    
    /**
     * Connect to LSL bridge
     * 
     * @param {string} url - WebSocket URL of LSL bridge
     */
    connectLSL(url = 'ws://localhost:8765') {
        try {
            const ws = new WebSocket(url);
            ws.onopen = () => {
                console.log('[LSL] Connected');
                this.lslOutlet = {
                    push_sample: (data) => ws.send(JSON.stringify({
                        type: 'marker',
                        data
                    }))
                };
            };
            ws.onerror = (e) => console.warn('[LSL] Connection error:', e);
            ws.onclose = () => {
                console.log('[LSL] Disconnected');
                this.lslOutlet = null;
            };
        } catch (e) {
            console.warn('[LSL] Failed to connect:', e);
        }
    }
    
    /**
     * Generic WebSocket integration
     */
    sendToWebSocket(entry) {
        if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
            return;
        }
        
        try {
            this.webSocket.send(JSON.stringify({
                type: 'eeg_event',
                ...entry
            }));
        } catch (e) {
            console.warn('WebSocket send failed:', e);
        }
    }
    
    /**
     * Connect to generic WebSocket bridge
     */
    connectWebSocket(url) {
        try {
            this.webSocket = new WebSocket(url);
            this.webSocket.onopen = () => console.log('[WebSocket] Connected');
            this.webSocket.onerror = (e) => console.warn('[WebSocket] Error:', e);
        } catch (e) {
            console.warn('[WebSocket] Failed to connect:', e);
        }
    }
    
    /**
     * Parallel port trigger integration
     * Requires local bridge service (e.g., Python with pyparallel)
     */
    sendToParallelPort(entry) {
        if (!this.parallelPort) return;
        
        try {
            // Send trigger code via HTTP to local service
            fetch(this.parallelPort.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: entry.numericCode,
                    duration: 10  // Trigger pulse duration in ms
                })
            }).catch(() => {});  // Ignore fetch errors for timing
        } catch (e) {
            // Silently fail to avoid timing disruption
        }
    }
    
    /**
     * Configure parallel port bridge
     */
    configureParallelPort(url = 'http://localhost:8888/trigger') {
        this.parallelPort = { url };
        console.log('[ParallelPort] Configured:', url);
    }
    
    // ============================================================
    // EXPORT / ANALYSIS
    // ============================================================
    
    /**
     * Export all logged events as JSON
     */
    exportJSON() {
        return JSON.stringify(this.entries, null, 2);
    }
    
    /**
     * Export as CSV for analysis
     */
    exportCSV() {
        if (this.entries.length === 0) return '';
        
        const headers = [
            'eventType',
            'absoluteTime',
            'relativeTime',
            'numericCode',
            'stimulusType',
            'stimulusCode',
            'trialNumber',
            'actualDurationMs'
        ];
        
        const rows = this.entries.map(entry => 
            headers.map(h => entry[h] !== undefined ? entry[h] : '').join(',')
        );
        
        return [headers.join(','), ...rows].join('\n');
    }
    
    /**
     * Download log as file
     */
    downloadLog(format = 'json') {
        const content = format === 'csv' ? this.exportCSV() : this.exportJSON();
        const blob = new Blob([content], { 
            type: format === 'csv' ? 'text/csv' : 'application/json' 
        });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `eeg_events_${Date.now()}.${format}`;
        a.click();
        
        URL.revokeObjectURL(url);
    }
    
    /**
     * Get summary statistics
     */
    getSummary() {
        const onsets = this.entries.filter(e => e.eventType === 'STIM_ONSET');
        const offsets = this.entries.filter(e => e.eventType === 'STIM_OFFSET');
        
        return {
            totalEvents: this.entries.length,
            totalTrials: onsets.length,
            completedTrials: offsets.length,
            experimentDuration: this.entries.length > 0 
                ? this.entries[this.entries.length - 1].relativeTime 
                : 0,
            eventTypes: [...new Set(this.entries.map(e => e.eventType))]
        };
    }
}

// Singleton instance
export const EventLogger = new EventLoggerClass();
export default EventLogger;