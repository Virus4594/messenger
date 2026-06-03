// groups.js - Полноценный групповой чат
let groupSocket = null;
let groupE2EE = null;
let groupId = null;
let currentUserId = null;
let currentUserRole = null;
let processedMessages = new Set();

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', async () => {
    groupId = document.getElementById('groupId')?.value;
    currentUserId = document.getElementById('currentUserId')?.value;
    currentUserRole = document.getElementById('currentUserRole')?.value;
    
    if (!groupId) {
        console.error('❌ Нет ID группы');
        return;
    }
    
    console.log('🚀 Запуск группового чата:', groupId);
    
    // Инициализируем E2EE
    groupE2EE = new GroupE2EE(groupId, currentUserId);
    await groupE2EE.init();
    
    initGroupSocket();
    await loadGroupMessages();
    setupGroupEventListeners();
    await loadGroupStickers();
});

function initGroupSocket() {
    groupSocket = io({ transports: ['websocket', 'polling'] });
    
    groupSocket.on('connect', () => {
        console.log('✅ WebSocket группы подключён');
        groupSocket.emit('join_group', { group_id: parseInt(groupId) });
    });
    
    groupSocket.on('new_group_message', async (data) => {
        if (processedMessages.has(data.id)) return;
        processedMessages.add(data.id);
        
        let displayText = data.encrypted || '📎 Вложение';
        
        if (groupE2EE && groupE2EE.ready && data.encrypted && data.iv) {
            const decrypted = await groupE2EE.decryptMessage(data.encrypted, data.iv);
            displayText = decrypted;
        }
        
        addMessageToDOM({
            id: data.id,
            text: displayText,
            sender_id: data.sender_id,
            sender_username: data.sender_username,
            created_at: data.created_at,
            is_mine: data.sender_id == currentUserId
        });
        
        // Уведомление
        if (data.sender_id != currentUserId && !document.hasFocus()) {
            playNotificationSound();
            showNotification(data.sender_username, displayText);
        }
    });
    
    groupSocket.on('group_typing', (data) => {
        if (data.sender_id != currentUserId) {
            const indicator = document.getElementById('groupTypingIndicator');
            const usernameSpan = document.getElementById('groupTypingUsername');
            if (indicator && usernameSpan) {
                usernameSpan.textContent = data.sender_username;
                indicator.style.display = 'flex';
                setTimeout(() => indicator.style.display = 'none', 3000);
            }
        }
    });
}

async function loadGroupMessages() {
    try {
        const response = await fetch(`/api/group-messages/${groupId}`);
        const data = await response.json();
        
        const container = document.getElementById('groupMessagesList');
        if (!container) return;
        
        container.innerHTML = '';
        processedMessages.clear();
        
        if (data.messages && data.messages.length > 0) {
            for (const msg of data.messages) {
                let displayText = msg.encrypted || '📎';
                
                if (groupE2EE && groupE2EE.ready && msg.encrypted && msg.nonce) {
                    displayText = await groupE2EE.decryptMessage(msg.encrypted, msg.nonce);
                }
                
                addMessageToDOM({
                    id: msg.id,
                    text: displayText,
                    sender_id: msg.sender_id,
                    sender_username: msg.sender_username,
                    created_at: msg.created_at,
                    is_mine: msg.sender_id == currentUserId
                });
            }
        } else {
            container.innerHTML = '<div class="empty-chat">💬 Напишите первое сообщение в группе!</div>';
        }
        
        scrollToBottom();
    } catch(e) {
        console.error('Load error:', e);
    }
}

function addMessageToDOM(msg) {
    const container = document.getElementById('groupMessagesList');
    if (!container) return;
    
    const loader = container.querySelector('.loading-messages');
    if (loader) loader.remove();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `group-message ${msg.is_mine ? 'sent' : 'received'}`;
    
    const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${(msg.sender_username || '?').charAt(0).toUpperCase()}</div>
        <div class="message-bubble">
            ${!msg.is_mine ? `<div class="message-sender">${escapeHtml(msg.sender_username)}</div>` : ''}
            <div class="message-text">${escapeHtml(msg.text)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    scrollToBottom();
}

async function sendGroupMessage() {
    const input = document.getElementById('groupMessageInput');
    const text = input.value.trim();
    
    if (!text) return;
    
    input.value = '';
    input.style.height = 'auto';
    
    let encrypted = text;
    let iv = null;
    
    if (groupE2EE && groupE2EE.ready) {
        const enc = await groupE2EE.encryptMessage(JSON.stringify({ type: 'text', text: text }));
        encrypted = enc.encrypted;
        iv = enc.iv;
    }
    
    if (groupSocket && groupSocket.connected) {
        groupSocket.emit('send_group_message', {
            group_id: parseInt(groupId),
            encrypted: encrypted,
            iv: iv,
            temp_id: 'temp_' + Date.now()
        });
    }
}

async function sendGroupSticker(stickerId, stickerCode) {
    let encrypted = null;
    let iv = null;
    
    if (groupE2EE && groupE2EE.ready) {
        const enc = await groupE2EE.encryptMessage(JSON.stringify({ type: 'sticker', code: stickerCode, id: stickerId }));
        encrypted = enc.encrypted;
        iv = enc.iv;
    }
    
    if (groupSocket && groupSocket.connected) {
        groupSocket.emit('send_group_message', {
            group_id: parseInt(groupId),
            encrypted: encrypted,
            iv: iv,
            is_sticker: true,
            sticker_id: stickerId,
            sticker_code: stickerCode
        });
    }
    
    document.getElementById('stickerPanel').style.display = 'none';
}

async function loadGroupStickers() {
    try {
        const response = await fetch('/api/stickers');
        const stickers = await response.json();
        
        const stickerGrid = document.querySelector('.sticker-grid');
        if (stickerGrid) {
            stickerGrid.innerHTML = '';
            stickers.forEach(sticker => {
                const stickerEl = document.createElement('div');
                stickerEl.className = 'sticker-item';
                stickerEl.innerHTML = `<span class="sticker-emoji">${sticker.code}</span>`;
                stickerEl.onclick = () => sendGroupSticker(sticker.id, sticker.code);
                stickerGrid.appendChild(stickerEl);
            });
        }
    } catch(e) {
        console.error('Stickers error:', e);
    }
}

function setupGroupEventListeners() {
    const sendBtn = document.getElementById('sendGroupButton');
    if (sendBtn) sendBtn.onclick = sendGroupMessage;
    
    const input = document.getElementById('groupMessageInput');
    if (input) {
        input.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendGroupMessage();
            }
        };
        
        input.oninput = function() {
            if (groupSocket && groupSocket.connected) {
                groupSocket.emit('group_typing', { group_id: parseInt(groupId) });
            }
        };
    }
    
    const stickerBtn = document.getElementById('stickerBtn');
    if (stickerBtn) {
        stickerBtn.onclick = () => {
            const panel = document.getElementById('stickerPanel');
            panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
        };
    }
    
    const membersBtn = document.getElementById('membersBtn');
    if (membersBtn) {
        membersBtn.onclick = () => {
            const sidebar = document.getElementById('membersSidebar');
            if (sidebar) {
                sidebar.style.display = sidebar.style.display === 'none' ? 'flex' : 'none';
            }
        };
    }
    
    const closeSidebar = document.getElementById('closeSidebar');
    if (closeSidebar) {
        closeSidebar.onclick = () => {
            document.getElementById('membersSidebar').style.display = 'none';
        };
    }
}

function scrollToBottom() {
    const area = document.getElementById('groupMessagesArea');
    if (area) setTimeout(() => area.scrollTop = area.scrollHeight, 100);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function playNotificationSound() {
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const context = new AudioCtx();
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.frequency.value = 880;
        gain.gain.value = 0.3;
        oscillator.start();
        gain.gain.exponentialRampToValueAtTime(0.00001, context.currentTime + 0.3);
        oscillator.stop(context.currentTime + 0.3);
        if (context.state === 'suspended') context.resume();
    } catch(e) {}
}

function showNotification(username, message) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (document.hasFocus()) return;
    
    const notification = new Notification(`📨 ${username} в группе`, {
        body: message.length > 60 ? message.substring(0, 60) + '...' : message,
        icon: '/static/favicon.ico'
    });
    notification.onclick = () => window.focus();
}

// Запрашиваем разрешение на уведомления
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}