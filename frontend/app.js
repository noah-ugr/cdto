// ============== CONFIGURATION ==============
const API_BASE_URL = 'http://localhost:8000';
const RECONNECT_INTERVAL = 3000; // ms
const MAX_RECONNECT_ATTEMPTS = 10;

// ============== GLOBAL STATE ==============
let state = {
    isConnected: false,
    reconnectAttempts: 0,
    currentConfig: null,
    threadId: 'session_web_demo',
    episodicMemoryEnabled: true,
    isSending: false,
    lastXaiReport: null,
    lastEpisodicXaiReport: null,
    visualizations: null
};

// ============== DOM ELEMENTS ==============
const messagesContainer = document.getElementById('messages-container');
const messageInput = document.getElementById('message-input');
const chatForm = document.getElementById('chat-form');
const configContent = document.getElementById('config-content');
const logsContainer = document.getElementById('logs-container');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const clearChatBtn = document.getElementById('clear-chat-btn');
const clearLogsBtn = document.getElementById('clear-logs-btn');
const resetConfigBtn = document.getElementById('reset-config-btn');
const toggleConfigBtn = document.getElementById('toggle-config-btn');
const episodicMemoryToggle = document.getElementById('episodic-memory-toggle');
const configModal = document.getElementById('config-modal');
const IMAGE_PATH_REGEX = /([A-Za-z]:[\\/][^\s"'<>]+?\.(?:png|jpe?g|gif|webp|bmp)|\/[^\s"'<>]+?\.(?:png|jpe?g|gif|webp|bmp))/ig;

// ============== CONFIGURE MARKED.JS ==============
if (typeof marked !== 'undefined') {
    // Configure marked for GFM (GitHub Flavored Markdown) and tables
    marked.setOptions({
        gfm: true,
        breaks: true,
        tables: true,
        headerIds: false,
        mangle: false
    });
    console.log('✅ Marked.js configured successfully');
} else {
    console.warn('⚠️ Marked.js not loaded');
}

// ============== INITIALIZATION ==============
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Loaded, starting application...');
    initializeApp();
    setupEventListeners();
    setupWebSocketHealthCheck();
});

// ============== INITIALIZE APPLICATION ==============
function initializeApp() {
    checkConnection();
    loadInitialConfig();
    updateVisualizationButtons(); // Initialize buttons (disabled by default)
    loadBaselineOnStartup();
    addLog('CDTO started successfully', 'info');
}

function loadBaselineOnStartup() {
    // Load baseline
    fetch(`${API_BASE_URL}/simulation/baseline`)
        .then(res => res.json())
        .then(data => {
            if (data.available && data.baseline_report) {
                addMessage('🕵️ **xAI BASELINE REPORT (Cold Start)**\n\n' + data.baseline_report, 'assistant', 'xai-report');
                addLog('Baseline (cold start) loaded on screen', 'success');
            } else {
                addLog('Baseline not available yet', 'info');
            }
        })
        .catch(err => {
            addLog('Could not load baseline at startup: ' + err.message, 'warning');
        });
    
    // Load visualizations
    fetch(`${API_BASE_URL}/simulation/visualizations`)
        .then(res => res.json())
        .then(data => {
            if (data.available && data.visualizations) {
                state.visualizations = data.visualizations;
                updateVisualizationButtons();
                addLog('Visualizations loaded', 'success');
            }
        })
        .catch(err => {
            addLog('Could not load visualizations: ' + err.message, 'warning');
        });
}

// ============== EVENT LISTENERS ==============
function setupEventListeners() {
    // Chat
    chatForm.addEventListener('submit', handleFormSubmit);
    messageInput.addEventListener('keydown', handleKeyDown);
    
    // Buttons
    clearChatBtn.addEventListener('click', clearChat);
    clearLogsBtn.addEventListener('click', clearLogs);
    resetConfigBtn.addEventListener('click', resetConfig);
    toggleConfigBtn.addEventListener('click', openConfigModal);
    
    // Options
    episodicMemoryToggle.addEventListener('change', (e) => {
        state.episodicMemoryEnabled = e.target.checked;
        addLog(`Episodic memory ${e.target.checked ? 'enabled' : 'disabled'}`, 'info');
    });
    
    // Modal close
    document.querySelector('.modal-close')?.addEventListener('click', closeConfigModal);
    configModal?.addEventListener('click', (e) => {
        if (e.target === configModal) closeConfigModal();
    });
}

// ============== HEALTH CHECK ==============
function checkConnection() {
    fetch(`${API_BASE_URL}/health`)
        .then(res => res.json())
        .then(data => {
            state.isConnected = true;
            state.reconnectAttempts = 0;
            updateConnectionStatus(true);
            addLog('Connected to CDTO server', 'success');
            console.log('✅ Connected:', data);
        })
        .catch(err => {
            state.isConnected = false;
            updateConnectionStatus(false);
            addLog('Connection error: ' + err.message, 'error');
            console.error('❌ Connection error:', err);
            
            // Retry connection
            if (state.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                state.reconnectAttempts++;
                setTimeout(checkConnection, RECONNECT_INTERVAL);
            } else {
                addLog('Could not connect after ' + MAX_RECONNECT_ATTEMPTS + ' attempts', 'error');
            }
        });
}

function setupWebSocketHealthCheck() {
    setInterval(checkConnection, 10000); // Every 10 seconds
}

function updateConnectionStatus(connected) {
    if (connected) {
        statusIndicator.classList.add('connected');
        statusText.textContent = 'Connected';
        messageInput.disabled = false;
    } else {
        statusIndicator.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        messageInput.disabled = true;
    }
}

// ============== LOAD INITIAL CONFIGURATION ==============
function loadInitialConfig() {
    if (!state.isConnected) {
        addLog('Not connected. Retrying...', 'warning');
        setTimeout(loadInitialConfig, 2000);
        return;
    }

    fetch(`${API_BASE_URL}/config/current`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            state.currentConfig = data.config;
            updateConfigDisplay(data.config);
            addLog('Configuration loaded', 'success');
        })
        .catch(err => {
            addLog('Error loading config: ' + err.message, 'error');
            console.error('Error:', err);
        });
}

// ============== CHAT HANDLER ==============
function handleFormSubmit(e) {
    e.preventDefault();
    const message = messageInput.value.trim();
    
    if (!message) return;
    if (!state.isConnected) {
        addLog('Not connected to server', 'error');
        return;
    }
    if (state.isSending) {
        addLog('Waiting for previous response...', 'warning');
        return;
    }

    // Show user message
    addMessage(message, 'user');
    messageInput.value = '';
    messageInput.focus();
    
    // Show typing indicator
    showTypingIndicator();
    state.isSending = true;

    // Send to server
    sendChatMessage(message);
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
}

function sendChatMessage(message) {
    const payload = {
        message: message,
        thread_id: state.threadId,
        include_episodic_memory: state.episodicMemoryEnabled
    };

    fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => {
            removeTypingIndicator();
            state.isSending = false;

            if (data.success) {
                if (data.xai_report && data.xai_report.trim() !== '' && data.xai_report !== state.lastXaiReport) {
                    addMessage('🕵️ **xAI FORENSIC ANALYSIS**\n\n' + data.xai_report, 'assistant', 'xai-report');
                    addLog('xAI report generated', 'success');
                    state.lastXaiReport = data.xai_report;
                }
                
                if (data.episodic_xai_report && data.episodic_xai_report.trim() !== '' && data.episodic_xai_report !== state.lastEpisodicXaiReport) {
                    addMessage('🕵️ **xAI FORENSIC ANALYSIS (Episodic)**\n\n' + data.episodic_xai_report, 'assistant', 'xai-report');
                    addLog('Episodic xAI report generated', 'success');
                    state.lastEpisodicXaiReport = data.episodic_xai_report;
                }
                
                // Update visualizations and show/hide buttons
                if (data.visualizations) {
                    state.visualizations = data.visualizations;
                    updateVisualizationButtons();
                    addLog('Visualizations available', 'success');
                }
                
                if (data.response) {
                    addMessage(data.response, 'assistant');
                }
                addLog('Response received', 'success');

                if (data.current_config) {
                    state.currentConfig = data.current_config;
                    updateConfigDisplay(data.current_config);
                }

                if (data.execution_log && data.execution_log.length > 0) {
                    data.execution_log.forEach(log => {
                        addLog(log, 'info');
                    });
                }

                if (data.validation_errors && data.validation_errors.length > 0) {
                    addMessage('⚠️ Validation errors detected', 'system');
                    data.validation_errors.forEach(err => {
                        addLog(err, 'error');
                    });
                }
            } else {
                addMessage(`Error: ${data.message || 'Unknown error'}`, 'error');
                addLog(data.message || 'Error in response', 'error');
            }
        })
        .catch(err => {
            removeTypingIndicator();
            state.isSending = false;
            addMessage(`Connection error: ${err.message}`, 'error');
            addLog('Error: ' + err.message, 'error');
            console.error('Error:', err);
        });
}

// ============== MESSAGES ==============
function addMessage(content, type = 'assistant', extraClass = '') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    if (extraClass) {
        messageDiv.classList.add(extraClass);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessageContent(content, type);
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatMessageContent(content, type = 'assistant') {
    let text = String(content ?? '');

    if (type === 'user') {
        return escapeHtml(text).replace(/\n/g, '<br>');
    }
    
    // If it is type 'visualization', return raw HTML without processing
    if (type === 'visualization') {
        console.log('📊 Visualization HTML (unprocessed):', text.substring(0, 200));
        return text;
    }

    // Convert local image paths into renderable markdown images via backend proxy.
    text = convertImagePathsToMarkdown(text);

    // For assistant messages: use marked.js for full Markdown support
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        try {
            // Parse Markdown with marked.js
            const rawHtml = marked.parse(text);
            // Sanitize with DOMPurify for security
            const cleanHtml = DOMPurify.sanitize(rawHtml, {
                ALLOWED_TAGS: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'code', 'pre', 'blockquote', 'a', 'div', 'span', 'img'],
                ALLOWED_ATTR: ['href', 'class', 'id', 'src', 'alt', 'title', 'loading', 'style', 'onclick']
            });
            return cleanHtml;
        } catch (err) {
            console.error('Error parsing markdown:', err);
            // Fallback to escaped text
            return escapeHtml(text).replace(/\n/g, '<br>');
        }
    }

    // Fallback if marked.js is not available
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function convertImagePathsToMarkdown(text) {
    if (!text || (text.includes('![') && text.includes(']('))) {
        return text;
    }

    return text
        .split('\n')
        .map(line => {
            if (!IMAGE_PATH_REGEX.test(line)) {
                IMAGE_PATH_REGEX.lastIndex = 0;
                return line;
            }
            IMAGE_PATH_REGEX.lastIndex = 0;

            return line.replace(IMAGE_PATH_REGEX, (rawPath) => {
                const src = buildImageProxyUrl(rawPath);
                return `\n![Generated image](${src})\n`;
            });
        })
        .join('\n');
}

function buildImageProxyUrl(localPath) {
    const normalizedPath = String(localPath).replace(/\\/g, '/').trim();
    return `${API_BASE_URL}/assets/image?path=${encodeURIComponent(normalizedPath)}`;
}

// parseMarkdownTables removed - now handled by marked.js

function clearChat() {
    const welcome = messagesContainer.querySelector('.welcome-message');
    messagesContainer.innerHTML = '';
    if (welcome) {
        messagesContainer.appendChild(welcome);
    }
    state.lastXaiReport = null;
    state.lastEpisodicXaiReport = null;
    addLog('Chat cleared - xAI reports reset', 'info');
}

// ============== TYPING INDICATOR ==============
function showTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = 'typing-indicator';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

// ============== LOGS ==============
function addLog(message, level = 'info') {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${level}`;
    
    const now = new Date().toLocaleTimeString();
    logEntry.innerHTML = `
        <span class="log-time">[${now}]</span>
        <span class="log-message">${escapeHtml(String(message ?? ''))}</span>
    `;
    
    logsContainer.appendChild(logEntry);
    logsContainer.scrollTop = logsContainer.scrollHeight;
    
    // Limit displayed logs (max 100)
    const logs = logsContainer.querySelectorAll('.log-entry');
    if (logs.length > 100) {
        logs[0].remove();
    }
}

function clearLogs() {
    logsContainer.innerHTML = '';
    addLog('Logs cleared', 'info');
}

// ============== CONFIGURATION ==============
function updateConfigDisplay(config) {
    if (!config) {
        configContent.innerHTML = '<div class="config-loading">No configuration available</div>';
        return;
    }

    let html = '';
    
    // Show main properties
    const mainProps = ['runId', 'Teams', 'Simulation_period'];
    mainProps.forEach(prop => {
        if (prop in config) {
            html += `
                <div class="config-item">
                    <label class="config-label">${prop}</label>
                    <div class="config-value">${JSON.stringify(config[prop])}</div>
                </div>
            `;
        }
    });

    // Show tasks if they exist
    if (config.A001 && config.A001.tasks) {
        html += `
            <div class="config-item">
                <label class="config-label">📋 Tasks</label>
                <div class="config-value">${Object.keys(config.A001.tasks).length} configured tasks</div>
            </div>
        `;
    }

    if (config.A001) {
        html += `
            <div class="config-item">
                <label class="config-label">Team</label>
                <div class="config-value">${config.A001.Team || 'N/A'}</div>
            </div>
        `;
        html += `
            <div class="config-item">
                <label class="config-label">Team Members</label>
                <div class="config-value">${config.A001['Team members'] || 'N/A'}</div>
            </div>
        `;
    }

    configContent.innerHTML = html;
}

function resetConfig() {
    if (!state.isConnected) {
        addLog('Not connected', 'error');
        return;
    }

    if (!confirm('Reset to initial configuration?')) return;

    fetch(`${API_BASE_URL}/config/reset`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                state.currentConfig = data.config;
                updateConfigDisplay(data.config);
                addLog('Configuration reset', 'success');
                addMessage('✅ Configuration reset to initial values', 'system');
            }
        })
        .catch(err => addLog('Error: ' + err.message, 'error'));
}

function openConfigModal() {
    configModal.classList.add('active');
    const modalBody = document.getElementById('modal-config-json');
    modalBody.textContent = JSON.stringify(state.currentConfig, null, 2);
}

function closeConfigModal() {
    configModal.classList.remove('active');
}

function copyConfigJson() {
    const text = document.getElementById('modal-config-json').textContent;
    navigator.clipboard.writeText(text).then(() => {
        addLog('JSON copied to clipboard', 'success');
    });
}

// ============== FLOATING FUNCTIONS ==============
function showSystemInfo() {
    if (!state.isConnected) {
        addLog('Not connected', 'error');
        return;
    }

    fetch(`${API_BASE_URL}/info`)
        .then(res => res.json())
        .then(data => {
            addMessage(`
🤖 **CDTO System Info**
- Status: ${data.status}
- Version: ${data.version}
- Description: ${data.description}
- Capabilities:
${data.capabilities.map(c => `  • ${c}`).join('\n')}
            `, 'assistant');
        })
        .catch(err => addLog('Error: ' + err.message, 'error'));
}

function showBaseline() {
    if (!state.isConnected) {
        addLog('Not connected', 'error');
        return;
    }

    fetch(`${API_BASE_URL}/simulation/baseline`)
        .then(res => res.json())
        .then(data => {
            if (data.available) {
                addMessage(`📊 **Baseline Report**\n\n${data.baseline_report}`, 'assistant');
            } else {
                addMessage('ℹ️ No baseline report available', 'system');
            }
        })
        .catch(err => addLog('Error: ' + err.message, 'error'));
}

// ============== VISUALIZATIONS ==============
function updateVisualizationButtons() {
    const bottleneckBtn = document.getElementById('fab-bottleneck');
    const ganttBtn = document.getElementById('fab-gantt');
    
    console.log('🎨 Updating visualization buttons...', state.visualizations);
    
    if (!bottleneckBtn || !ganttBtn) {
        console.error('❌ Visualization buttons not found in DOM');
        return;
    }
    
    if (state.visualizations) {
        console.log('✅ Visualizations available:', {
            bottleneck: !!state.visualizations.bottleneck_heatmap,
            gantt_count: state.visualizations.gantt_charts?.length || 0
        });
        
        if (state.visualizations.bottleneck_heatmap) {
            bottleneckBtn.style.display = 'flex';
            bottleneckBtn.disabled = false;
            bottleneckBtn.style.opacity = '1';
            console.log('🔥 Bottleneck button enabled');
        } else {
            bottleneckBtn.style.display = 'flex';
            bottleneckBtn.disabled = true;
            bottleneckBtn.style.opacity = '0.4';
            bottleneckBtn.title = 'No bottleneck heatmap available';
        }
        
        if (state.visualizations.gantt_charts && state.visualizations.gantt_charts.length > 0) {
            ganttBtn.style.display = 'flex';
            ganttBtn.disabled = false;
            ganttBtn.style.opacity = '1';
            console.log('📊 Gantt button enabled');
        } else {
            ganttBtn.style.display = 'flex';
            ganttBtn.disabled = true;
            ganttBtn.style.opacity = '0.4';
            ganttBtn.title = 'No Gantt charts available';
        }
    } else {
        console.log('⚠️ No visualizations loaded yet');
        // Show disabled buttons
        bottleneckBtn.style.display = 'flex';
        bottleneckBtn.disabled = true;
        bottleneckBtn.style.opacity = '0.4';
        bottleneckBtn.title = 'Run a simulation first';
        
        ganttBtn.style.display = 'flex';
        ganttBtn.disabled = true;
        ganttBtn.style.opacity = '0.4';
        ganttBtn.title = 'Run a simulation first';
    }
}

function showBottleneckHeatmap() {
    if (!state.visualizations || !state.visualizations.bottleneck_heatmap) {
        addMessage('ℹ️ No bottleneck heatmap available', 'system');
        return;
    }
    
    const imagePath = state.visualizations.bottleneck_heatmap;
    console.log('🔥 Raw image path:', imagePath);
    
    const encodedPath = encodeURIComponent(imagePath);
    const imageUrl = `${API_BASE_URL}/assets/image?path=${encodedPath}`;
    console.log('🔥 Final image URL:', imageUrl);
    
    const imageHtml = `<div class="visualization-container"><h3>🔥 Bottleneck Heatmap</h3><img src="${imageUrl}" alt="Bottleneck Heatmap" class="visualization-image" style="cursor: pointer;" title="Click to open in a new window" onclick="window.open('${imageUrl}')"><p class="visualization-hint">💡 Click the image to enlarge it</p></div>`;
    
    addMessage(imageHtml, 'visualization');
    addLog('Bottleneck heatmap displayed', 'success');
}

function showGanttCharts() {
    if (!state.visualizations || !state.visualizations.gantt_charts || state.visualizations.gantt_charts.length === 0) {
        addMessage('ℹ️ No Gantt charts available', 'system');
        return;
    }
    
    console.log('📊 Gantt charts:', state.visualizations.gantt_charts);
    
    let ganttHtml = '<div class="visualization-container"><h3>📊 Gantt Charts</h3>';
    
    state.visualizations.gantt_charts.forEach((chartPath, index) => {
        console.log(`📊 Processing chart ${index}:`, chartPath);
        
        const encodedPath = encodeURIComponent(chartPath);
        const imageUrl = `${API_BASE_URL}/assets/image?path=${encodedPath}`;
        const chartName = chartPath.split(/[\\/]/).pop().replace('.png', '').replace('gantt_', '');
        
        console.log(`📊 Chart ${index} URL:`, imageUrl);
        
        ganttHtml += `<div class="gantt-chart-item"><h4>Activity: ${chartName}</h4><img src="${imageUrl}" alt="Gantt Chart - ${chartName}" class="visualization-image" style="cursor: pointer;" title="Click to open in a new window" onclick="window.open('${imageUrl}')"></div>`;
    });
    
    ganttHtml += '<p class="visualization-hint">💡 Click any image to enlarge it</p></div>';
    
    addMessage(ganttHtml, 'visualization');
    addLog(`${state.visualizations.gantt_charts.length} Gantt charts displayed`, 'success');
}

// ============== UTILITIES ==============
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============== DEBUG ==============
console.log('App.js loaded successfully');
