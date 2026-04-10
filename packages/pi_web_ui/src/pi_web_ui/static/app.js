/**
 * Pi Web UI - Main Application JavaScript
 * 
 * Handles WebSocket connection, message rendering, and UI interactions.
 */

// Global state
const state = {
    sessionId: null,
    ws: null,
    isStreaming: false,
    currentModel: 'openai/gpt-4o',
    models: [],
    attachments: [],
    messages: [],
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
};

// DOM Elements
const elements = {
    messages: document.getElementById('messages'),
    streamingMessage: document.getElementById('streaming-message'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    abortBtn: document.getElementById('abort-btn'),
    attachBtn: document.getElementById('attach-btn'),
    fileInput: document.getElementById('file-input'),
    attachmentsPreview: document.getElementById('attachments-preview'),
    sessionList: document.getElementById('session-list'),
    newChatBtn: document.getElementById('new-chat-btn'),
    modelSelectorBtn: document.getElementById('model-selector-btn'),
    currentModelSpan: document.getElementById('current-model'),
    modelModal: document.getElementById('model-modal'),
    modelList: document.getElementById('model-list'),
    modalClose: document.querySelector('.modal-close'),
    tokenStats: document.getElementById('token-stats'),
};

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    // Load session ID from URL or create new
    const urlParams = new URLSearchParams(window.location.search);
    state.sessionId = urlParams.get('session') || generateId();
    
    // Update URL without reloading
    const url = new URL(window.location);
    url.searchParams.set('session', state.sessionId);
    window.history.replaceState({}, '', url);
    
    // Setup event listeners
    setupEventListeners();
    
    // Load models
    await loadModels();
    
    // Load sessions
    await loadSessions();
    
    // Connect WebSocket
    connectWebSocket();
    
    // Focus input
    elements.messageInput.focus();
}

function generateId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function setupEventListeners() {
    // Message input
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    elements.messageInput.addEventListener('input', autoResizeTextarea);
    
    // Send button
    elements.sendBtn.addEventListener('click', sendMessage);
    
    // Abort button
    elements.abortBtn.addEventListener('click', abortMessage);
    
    // Attach button
    elements.attachBtn.addEventListener('click', () => elements.fileInput.click());
    
    // File input
    elements.fileInput.addEventListener('change', handleFileSelect);
    
    // New chat button
    elements.newChatBtn.addEventListener('click', createNewChat);
    
    // Model selector
    elements.modelSelectorBtn.addEventListener('click', () => {
        elements.modelModal.classList.remove('hidden');
    });
    
    elements.modalClose.addEventListener('click', () => {
        elements.modelModal.classList.add('hidden');
    });
    
    elements.modelModal.addEventListener('click', (e) => {
        if (e.target === elements.modelModal || e.target.classList.contains('modal-overlay')) {
            elements.modelModal.classList.add('hidden');
        }
    });
    
    // Paste handler for images
    document.addEventListener('paste', handlePaste);
    
    // Drag and drop
    document.addEventListener('dragover', (e) => {
        e.preventDefault();
        document.body.classList.add('dragging');
    });
    
    document.addEventListener('dragleave', (e) => {
        if (e.relatedTarget === null) {
            document.body.classList.remove('dragging');
        }
    });
    
    document.addEventListener('drop', handleDrop);
}

function autoResizeTextarea() {
    const textarea = elements.messageInput;
    textarea.style.height = 'auto';
    const newHeight = Math.min(textarea.scrollHeight, 200);
    textarea.style.height = newHeight + 'px';
}

function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws/${state.sessionId}`;
    state.ws = new WebSocket(wsUrl);
    
    state.ws.onopen = () => {
        console.log('WebSocket connected');
        state.reconnectAttempts = 0;
    };
    
    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    state.ws.onclose = () => {
        console.log('WebSocket closed');
        if (state.reconnectAttempts < state.maxReconnectAttempts) {
            state.reconnectAttempts++;
            setTimeout(connectWebSocket, 1000 * state.reconnectAttempts);
        }
    };
    
    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'connected':
            state.messages = data.messages || [];
            renderMessages();
            break;
            
        case 'stream_event':
            handleStreamEvent(data.event);
            break;
            
        case 'state':
            state.messages = data.state.messages || [];
            renderMessages();
            break;
            
        case 'error':
            showError(data.message);
            break;
            
        case 'pong':
            break;
    }
}

function handleStreamEvent(event) {
    switch (event.type) {
        case 'message_start':
            state.isStreaming = true;
            updateInputState();
            elements.streamingMessage.innerHTML = '';
            elements.streamingMessage.classList.remove('hidden');
            break;
            
        case 'message_update':
            if (event.message) {
                renderStreamingMessage(event.message);
            }
            break;
            
        case 'message_end':
            state.isStreaming = false;
            updateInputState();
            elements.streamingMessage.classList.add('hidden');
            if (event.message) {
                state.messages.push(event.message);
                renderMessages();
            }
            break;
            
        case 'tool_execution_start':
            renderToolCall(event, 'running');
            break;
            
        case 'tool_execution_end':
            updateToolCallResult(event);
            break;
            
        case 'agent_end':
            state.isStreaming = false;
            updateInputState();
            elements.streamingMessage.classList.add('hidden');
            updateTokenStats();
            break;
    }
}

async function sendMessage() {
    const content = elements.messageInput.value.trim();
    if (!content && state.attachments.length === 0) return;
    if (state.isStreaming) return;
    
    // Add user message to UI immediately
    const userMessage = {
        role: 'user',
        content: content,
        attachments: [...state.attachments],
    };
    state.messages.push(userMessage);
    renderMessages();
    
    // Clear input
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';
    state.attachments = [];
    renderAttachments();
    
    // Send via WebSocket
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({
            type: 'message',
            content: content,
            attachments: state.attachments.map(att => ({
                id: att.id,
                type: att.type,
                filename: att.filename,
                content_type: att.content_type,
                size: att.size,
                content: att.content,
                extracted_text: att.extracted_text,
                preview: att.preview,
            })),
            model_id: state.currentModel,
        }));
    }
}

function abortMessage() {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'abort' }));
    }
}

function renderMessages() {
    elements.messages.innerHTML = state.messages.map(msg => renderMessage(msg)).join('');
    highlightCode();
    scrollToBottom();
}

function renderMessage(msg) {
    if (msg.role === 'user') {
        return renderUserMessage(msg);
    } else if (msg.role === 'assistant') {
        return renderAssistantMessage(msg);
    } else if (msg.role === 'toolResult') {
        return '';
    }
    return '';
}

function renderUserMessage(msg) {
    const content = typeof msg.content === 'string' 
        ? escapeHtml(msg.content) 
        : renderContentArray(msg.content);
    
    const attachmentsHtml = msg.attachments?.length 
        ? `<div class="message-attachments">${msg.attachments.map(renderAttachmentTile).join('')}</div>`
        : '';
    
    return `
        <div class="message user">
            <div class="message-avatar">You</div>
            <div class="message-content">
                <p>${content}</p>
                ${attachmentsHtml}
            </div>
        </div>
    `;
}

function renderAssistantMessage(msg) {
    const content = typeof msg.content === 'string'
        ? marked.parse(msg.content)
        : renderContentArray(msg.content);
    
    const errorHtml = msg.stop_reason === 'error' && msg.error_message
        ? `<div class="error-message"><strong>Error:</strong> ${escapeHtml(msg.error_message)}</div>`
        : '';
    
    const usageHtml = msg.usage 
        ? `<div class="token-stats">${formatUsage(msg.usage)}</div>`
        : '';
    
    return `
        <div class="message assistant">
            <div class="message-avatar">AI</div>
            <div class="message-content">
                ${content}
                ${errorHtml}
                ${usageHtml}
            </div>
        </div>
    `;
}

function renderContentArray(content) {
    if (!Array.isArray(content)) return '';
    
    return content.map(c => {
        if (c.type === 'text') {
            return marked.parse(c.text || '');
        } else if (c.type === 'thinking') {
            return renderThinkingBlock(c.thinking || '');
        } else if (c.type === 'toolCall') {
            return renderToolCallBlock(c);
        }
        return '';
    }).join('');
}

function renderThinkingBlock(content) {
    return `
        <div class="thinking-block">
            <div class="thinking-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                <span>⚟</span> Thinking (click to expand)
            </div>
            <div class="thinking-content hidden">${escapeHtml(content)}</div>
        </div>
    `;
}

function renderToolCallBlock(toolCall) {
    const args = JSON.stringify(toolCall.arguments || {}, null, 2);
    return `
        <div class="tool-call" id="tool-${toolCall.id}">
            <div class="tool-call-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                <span class="tool-icon">⚙</span>
                <span class="tool-name">${escapeHtml(toolCall.name)}</span>
                <span class="tool-status">Running...</span>
            </div>
            <div class="tool-call-content hidden">
                <div class="tool-call-args">
                    <div class="tool-call-label">Arguments:</div>
                    <pre><code class="language-json">${escapeHtml(args)}</code></pre>
                </div>
            </div>
        </div>
    `;
}

function renderToolCall(event, status) {
    const existing = document.getElementById(`tool-${event.tool_call_id}`);
    if (existing) return;
    
    const html = renderToolCallBlock({
        id: event.tool_call_id,
        name: event.tool_name,
        arguments: event.args || {},
    });
    
    elements.streamingMessage.insertAdjacentHTML('beforeend', html);
}

function updateToolCallResult(event) {
    const toolEl = document.getElementById(`tool-${event.tool_call_id}`);
    if (!toolEl) return;
    
    const statusEl = toolEl.querySelector('.tool-status');
    if (statusEl) {
        statusEl.textContent = event.is_error ? 'Error' : 'Completed';
    }
    
    const contentEl = toolEl.querySelector('.tool-call-content');
    if (contentEl && event.result) {
        const resultHtml = `
            <div class="tool-call-result">
                <div class="tool-call-label">Result:</div>
                <pre><code>${escapeHtml(JSON.stringify(event.result, null, 2))}</code></pre>
            </div>
        `;
        contentEl.insertAdjacentHTML('beforeend', resultHtml);
    }
}

function renderStreamingMessage(message) {
    const html = typeof message.content === 'string'
        ? marked.parse(message.content)
        : renderContentArray(message.content);
    
    elements.streamingMessage.innerHTML = html + '<span class="streaming-cursor"></span>';
    highlightCode();
    scrollToBottom();
}

function renderAttachmentTile(att) {
    const preview = att.type === 'image' 
        ? `<img src="data:${att.content_type};base64,${att.preview || att.content}" alt="">`
        : '<span>Ὄ4</span>';
    
    return `
        <div class="attachment-tile" title="${escapeHtml(att.filename)}">
            ${preview}
            <span class="attachment-name">${escapeHtml(att.filename)}</span>
        </div>
    `;
}

async function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    await processFiles(files);
}

async function handlePaste(e) {
    const items = e.clipboardData?.items;
    if (!items) return;
    
    const imageFiles = [];
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith('image/')) {
            const file = items[i].getAsFile();
            if (file) imageFiles.push(file);
        }
    }
    
    if (imageFiles.length > 0) {
        e.preventDefault();
        await processFiles(imageFiles);
    }
}

async function handleDrop(e) {
    e.preventDefault();
    document.body.classList.remove('dragging');
    
    const files = Array.from(e.dataTransfer?.files || []);
    await processFiles(files);
}

async function processFiles(files) {
    for (const file of files) {
        try {
            const attachment = await createAttachment(file);
            state.attachments.push(attachment);
        } catch (error) {
            console.error('Failed to process file:', error);
            showError(`Failed to process ${file.name}`);
        }
    }
    renderAttachments();
}

async function createAttachment(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = reader.result.split(',')[1];
            resolve({
                id: generateId(),
                type: file.type.startsWith('image/') ? 'image' : 'document',
                filename: file.name,
                content_type: file.type,
                size: file.size,
                content: base64,
                preview: file.type.startsWith('image/') ? base64 : null,
            });
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function renderAttachments() {
    if (state.attachments.length === 0) {
        elements.attachmentsPreview.classList.add('hidden');
        return;
    }
    
    elements.attachmentsPreview.classList.remove('hidden');
    elements.attachmentsPreview.innerHTML = state.attachments.map((att, index) => `
        <div class="attachment-preview">
            ${att.preview 
                ? `<img src="data:${att.content_type};base64,${att.preview}" alt="">`
                : '<span>Ὄ4</span>'
            }
            <span>${escapeHtml(att.filename)}</span>
            <button class="remove-attachment" onclick="removeAttachment(${index})">×</button>
        </div>
    `).join('');
}

function removeAttachment(index) {
    state.attachments.splice(index, 1);
    renderAttachments();
}

async function loadModels() {
    try {
        const response = await fetch('/api/models');
        state.models = await response.json();
        renderModelList();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

function renderModelList() {
    elements.modelList.innerHTML = state.models.map(model => `
        <div class="model-item ${model.id === state.currentModel ? 'selected' : ''}" data-model="${model.id}">
            <span class="model-provider">${escapeHtml(model.provider)}</span>
            <span class="model-name">${escapeHtml(model.name)}</span>
        </div>
    `).join('');
    
    elements.modelList.querySelectorAll('.model-item').forEach(item => {
        item.addEventListener('click', () => {
            state.currentModel = item.dataset.model;
            const model = state.models.find(m => m.id === state.currentModel);
            elements.currentModelSpan.textContent = model?.name || state.currentModel;
            elements.modelModal.classList.add('hidden');
            renderModelList();
        });
    });
}

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();
        renderSessionList(sessions);
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

function renderSessionList(sessions) {
    elements.sessionList.innerHTML = sessions.map(session => `
        <div class="session-item ${session.id === state.sessionId ? 'active' : ''}" data-session="${session.id}">
            <div class="session-title">${escapeHtml(session.title || 'New Chat')}</div>
            <div class="session-preview">${escapeHtml(session.preview || '')}</div>
        </div>
    `).join('');
    
    elements.sessionList.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', () => {
            const sessionId = item.dataset.session;
            if (sessionId !== state.sessionId) {
                window.location.href = `/?session=${sessionId}`;
            }
        });
    });
}

function createNewChat() {
    const newSessionId = generateId();
    window.location.href = `/?session=${newSessionId}`;
}

function updateInputState() {
    if (state.isStreaming) {
        elements.sendBtn.classList.add('hidden');
        elements.abortBtn.classList.remove('hidden');
        elements.messageInput.disabled = true;
    } else {
        elements.sendBtn.classList.remove('hidden');
        elements.abortBtn.classList.add('hidden');
        elements.messageInput.disabled = false;
        elements.messageInput.focus();
    }
}

function updateTokenStats() {
    // Calculate total usage from messages
    let total = { input: 0, output: 0, cost: 0 };
    state.messages.forEach(msg => {
        if (msg.usage) {
            total.input += msg.usage.input || 0;
            total.output += msg.usage.output || 0;
            total.cost += msg.usage.cost?.total || 0;
        }
    });
    
    if (total.input || total.output) {
        elements.tokenStats.textContent = 
            `${total.input + total.output} tokens · $${total.cost.toFixed(4)}`;
    }
}

function formatUsage(usage) {
    const parts = [];
    if (usage.input) parts.push(`${usage.input} in`);
    if (usage.output) parts.push(`${usage.output} out`);
    if (usage.cache_read) parts.push(`${usage.cache_read} cache`);
    if (usage.cost?.total) parts.push(`$${usage.cost.total.toFixed(4)}`);
    return parts.join(' · ') || '';
}

function highlightCode() {
    document.querySelectorAll('pre code').forEach(block => {
        hljs.highlightElement(block);
    });
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    elements.messages.appendChild(errorDiv);
    scrollToBottom();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expose functions for inline event handlers
window.removeAttachment = removeAttachment;
