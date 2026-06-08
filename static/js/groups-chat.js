// groups-chat.js - Групповой чат (полностью как личка: файлы, фото, скачивание)

let groupSocket = null;
let groupE2EE = null;
let groupId = null;
let currentUserId = null;
let currentUsername = null;
let processedMessages = new Set();
let pendingTempIds = new Set();
let e2eeReadyPromise = null;

document.addEventListener('DOMContentLoaded', async () => {
    groupId = document.getElementById('groupId')?.value;
    currentUserId = document.getElementById('currentUserId')?.value;
    currentUsername = document.getElementById('currentUsername')?.value || 'Пользователь';
    
    if (!groupId) {
        console.error('❌ Нет ID группы');
        return;
    }
    
    console.log('🚀 Запуск группового чата:', groupId);
    
    if (typeof GroupE2EE !== 'undefined') {
        groupE2EE = new GroupE2EE(groupId, currentUserId);
        e2eeReadyPromise = groupE2EE.init();
        await e2eeReadyPromise;
        console.log('✅ E2EE инициализирован, ready:', groupE2EE.ready);
    }
    
    initSocket();
    await loadMessages();
    initButtons();
    loadStickers();
    initAttachments();
    
    console.log('✅ Групповой чат готов');
});

async function waitForE2EE() {
    if (groupE2EE && groupE2EE.ready) return true;
    if (e2eeReadyPromise) {
        console.log('⏳ Ожидание E2EE...');
        await e2eeReadyPromise;
        return groupE2EE?.ready || false;
    }
    return false;
}

// ========== WEBSOCKET ==========
function initSocket() {
    groupSocket = io();
    
    groupSocket.on('connect', () => {
        console.log('✅ WebSocket подключён');
        groupSocket.emit('join_group', { group_id: parseInt(groupId) });
    });
    
    groupSocket.on('new_group_message', async (data) => {
        console.log('📩 Получено:', data.id, 'is_attachment:', data.is_attachment);
        
        if (data.temp_id && pendingTempIds.has(data.temp_id)) {
            const temp = document.querySelector(`[data-temp="${data.temp_id}"]`);
            if (temp) temp.remove();
            pendingTempIds.delete(data.temp_id);
        }
        
        if (processedMessages.has(data.id)) return;
        if (document.querySelector(`[data-msg-id="${data.id}"]`)) return;
        processedMessages.add(data.id);
        
        let text = '';
        let isSticker = data.is_sticker || false;
        let stickerCode = data.sticker_code || '';
        let isAttachment = data.is_attachment || false;
        let attachmentName = data.attachment_name || '';
        let attachmentData = null;
        let attachmentMime = '';
        let attachmentSize = data.attachment_size || 0;
        
        // Расшифровка
        if (groupE2EE && groupE2EE.ready && data.encrypted && data.iv && data.mac) {
            try {
                const decrypted = await groupE2EE.decryptMessage(data.encrypted, data.iv, data.mac);
                if (typeof decrypted === 'object') {
                    if (decrypted.type === 'sticker') {
                        isSticker = true;
                        stickerCode = decrypted.code;
                        text = stickerCode;
                    } else if (decrypted.type === 'attachment') {
                        isAttachment = true;
                        attachmentData = decrypted.data;
                        attachmentName = decrypted.name;
                        attachmentMime = decrypted.mime;
                        attachmentSize = decrypted.size;
                        console.log('🔓 Вложение расшифровано:', attachmentName);
                    } else if (decrypted.type === 'text') {
                        text = decrypted.text || '';
                    } else {
                        text = decrypted.text || JSON.stringify(decrypted);
                    }
                } else {
                    text = decrypted;
                }
            } catch(e) {
                console.error('Decrypt error:', e);
                text = '🔒 Зашифровано';
            }
        } else if (data.encrypted && data.iv === 'plain') {
            try {
                const parsed = JSON.parse(data.encrypted);
                if (parsed.type === 'attachment') {
                    isAttachment = true;
                    attachmentData = parsed.data;
                    attachmentName = parsed.name;
                    attachmentMime = parsed.mime;
                    attachmentSize = parsed.size;
                } else {
                    text = data.encrypted;
                }
            } catch(e) {
                text = data.encrypted;
            }
        } else if (data.encrypted) {
            text = data.encrypted;
        }
        
        addMessageToDOM({
            id: data.id,
            text: text,
            sender_id: data.sender_id,
            sender_username: data.sender_username,
            created_at: data.created_at,
            is_sticker: isSticker,
            sticker_code: stickerCode,
            is_attachment: isAttachment,
            attachment_name: attachmentName,
            attachment_data: attachmentData,
            attachment_mime: attachmentMime,
            attachment_size: attachmentSize
        });
    });
}

// ========== ЗАГРУЗКА ИСТОРИИ ==========
async function loadMessages() {
    try {
        const res = await fetch(`/api/group-messages/${groupId}`);
        const data = await res.json();
        
        const container = document.getElementById('groupMessagesList');
        if (!container) return;
        
        container.innerHTML = '';
        processedMessages.clear();
        
        if (data.messages && data.messages.length > 0) {
            for (const msg of data.messages) {
                let text = '';
                let isSticker = msg.is_sticker || false;
                let stickerCode = msg.sticker_code || '';
                let isAttachment = msg.is_attachment || false;
                let attachmentName = msg.attachment_name || '';
                let attachmentData = null;
                let attachmentMime = '';
                let attachmentSize = msg.attachment_size || 0;
                
                if (groupE2EE && groupE2EE.ready && msg.encrypted && msg.iv && msg.mac) {
                    try {
                        const decrypted = await groupE2EE.decryptMessage(msg.encrypted, msg.iv, msg.mac);
                        if (typeof decrypted === 'object') {
                            if (decrypted.type === 'sticker') {
                                isSticker = true;
                                stickerCode = decrypted.code;
                                text = stickerCode;
                            } else if (decrypted.type === 'attachment') {
                                isAttachment = true;
                                attachmentData = decrypted.data;
                                attachmentName = decrypted.name;
                                attachmentMime = decrypted.mime;
                                attachmentSize = decrypted.size;
                            } else if (decrypted.type === 'text') {
                                text = decrypted.text || '';
                            } else {
                                text = decrypted.text || JSON.stringify(decrypted);
                            }
                        } else {
                            text = decrypted;
                        }
                    } catch(e) {
                        text = '🔒 Зашифровано';
                    }
                } else if (msg.encrypted && msg.iv === 'plain') {
                    try {
                        const parsed = JSON.parse(msg.encrypted);
                        if (parsed.type === 'attachment') {
                            isAttachment = true;
                            attachmentData = parsed.data;
                            attachmentName = parsed.name;
                            attachmentMime = parsed.mime;
                            attachmentSize = parsed.size;
                        } else {
                            text = msg.encrypted;
                        }
                    } catch(e) {
                        text = msg.encrypted;
                    }
                } else if (msg.encrypted) {
                    text = msg.encrypted;
                }
                
                addMessageToDOM({
                    id: msg.id,
                    text: text,
                    sender_id: msg.sender_id,
                    sender_username: msg.sender_username,
                    created_at: msg.created_at,
                    is_sticker: isSticker,
                    sticker_code: stickerCode,
                    is_attachment: isAttachment,
                    attachment_name: attachmentName,
                    attachment_data: attachmentData,
                    attachment_mime: attachmentMime,
                    attachment_size: attachmentSize
                });
            }
        } else {
            container.innerHTML = '<div class="empty">💬 Напишите первое сообщение!</div>';
        }
        
        scrollToBottom();
    } catch(e) {
        console.error('Load error:', e);
    }
}

// ========== ОТОБРАЖЕНИЕ (как в личке) ==========
function addMessageToDOM(msg) {
    const container = document.getElementById('groupMessagesList');
    if (!container) return;
    
    const empty = container.querySelector('.empty');
    if (empty) empty.remove();
    
    if (msg.id && !msg.id.toString().startsWith('temp')) {
        if (container.querySelector(`[data-msg-id="${msg.id}"]`)) return;
    }
    
    const isMine = msg.sender_id == currentUserId;
    const div = document.createElement('div');
    div.className = `msg ${isMine ? 'sent' : 'received'}`;
    div.setAttribute('data-msg-id', msg.id);
    if (msg.temp_id) div.setAttribute('data-temp', msg.temp_id);
    
    const time = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const avatar = (msg.sender_username || '?').charAt(0).toUpperCase();
    
    let content = '';
    
    if (msg.is_sticker) {
        content = `<div class="bubble sticker-bubble"><span class="sticker-emoji" style="font-size: 48px;">${escapeHtml(msg.sticker_code || '😊')}</span><div class="time">${time}</div></div>`;
    } 
    else if (msg.is_attachment && msg.attachment_data) {
        // Для изображений показываем превью + ссылка на скачивание
        if (msg.attachment_mime && msg.attachment_mime.startsWith('image/')) {
            content = `<div class="bubble">
                <img src="${msg.attachment_data}" style="max-width: 200px; max-height: 150px; border-radius: 12px; cursor: pointer;" onclick="window.open(this.src)">
                <div class="attachment-download" style="margin-top: 8px;">
                    <a href="${msg.attachment_data}" download="${escapeHtml(msg.attachment_name)}" style="font-size: 12px; color: #667eea; text-decoration: none;">📥 Скачать ${escapeHtml(msg.attachment_name)}</a>
                </div>
                <div class="time">${time}</div>
            </div>`;
        } else {
            // Обычные файлы
            content = `<div class="bubble">
                <a href="${msg.attachment_data}" download="${escapeHtml(msg.attachment_name)}" style="display: flex; align-items: center; gap: 8px; text-decoration: none; color: #667eea; padding: 8px 12px; background: #f0f0f0; border-radius: 12px;">
                    <span style="font-size: 24px;">📎</span>
                    <div>
                        <div style="font-weight: bold;">${escapeHtml(msg.attachment_name)}</div>
                        <div style="font-size: 10px; color: #666;">${formatFileSize(msg.attachment_size)}</div>
                    </div>
                    <span style="margin-left: auto;">⬇️</span>
                </a>
                <div class="time">${time}</div>
            </div>`;
        }
    } 
    else {
        content = `<div class="bubble"><div class="text">${escapeHtml(msg.text)}</div><div class="time">${time}</div></div>`;
    }
    
    div.innerHTML = `<div class="avatar">${avatar}</div>${content}`;
    container.appendChild(div);
    scrollToBottom();
}

// ========== ОТПРАВКА ТЕКСТА ==========
async function sendText() {
    const input = document.getElementById('groupMessageInput');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = '';
    input.style.height = 'auto';
    
    const tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    pendingTempIds.add(tempId);
    
    addMessageToDOM({
        id: tempId,
        temp_id: tempId,
        text: text,
        sender_id: currentUserId,
        sender_username: currentUsername,
        created_at: new Date().toISOString()
    });
    
    let encrypted = text;
    let iv = null;
    let mac = null;
    
    if (groupE2EE && groupE2EE.ready) {
        try {
            const enc = await groupE2EE.encryptMessage(JSON.stringify({ type: 'text', text: text }));
            encrypted = enc.encrypted;
            iv = enc.iv;
            mac = enc.mac;
        } catch(e) {}
    }
    
    if (groupSocket?.connected) {
        groupSocket.emit('send_group_message', {
            group_id: parseInt(groupId),
            encrypted: encrypted,
            iv: iv,
            mac: mac,
            temp_id: tempId,
            is_sticker: false,
            is_attachment: false
        });
    }
}

// ========== ОТПРАВКА СТИКЕРА ==========
async function sendSticker(stickerId, stickerCode) {
    const tempId = 'temp_sticker_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    pendingTempIds.add(tempId);
    
    addMessageToDOM({
        id: tempId,
        temp_id: tempId,
        text: stickerCode,
        sender_id: currentUserId,
        sender_username: currentUsername,
        created_at: new Date().toISOString(),
        is_sticker: true,
        sticker_code: stickerCode
    });
    
    let encrypted = null;
    let iv = null;
    let mac = null;
    
    if (groupE2EE && groupE2EE.ready) {
        try {
            const enc = await groupE2EE.encryptMessage(JSON.stringify({ type: 'sticker', code: stickerCode, id: stickerId }));
            encrypted = enc.encrypted;
            iv = enc.iv;
            mac = enc.mac;
        } catch(e) {}
    }
    
    if (groupSocket?.connected) {
        groupSocket.emit('send_group_message', {
            group_id: parseInt(groupId),
            encrypted: encrypted,
            iv: iv,
            mac: mac,
            temp_id: tempId,
            is_sticker: true,
            sticker_id: stickerId,
            sticker_code: stickerCode
        });
    }
    
    const panel = document.getElementById('stickerPanel');
    if (panel) panel.style.display = 'none';
}

// ========== ЗАГРУЗКА СТИКЕРОВ ==========
async function loadStickers() {
    try {
        const res = await fetch('/api/stickers');
        const stickers = await res.json();
        const grid = document.querySelector('.sticker-grid');
        if (grid) {
            grid.innerHTML = '';
            stickers.forEach(s => {
                const el = document.createElement('div');
                el.className = 'sticker-item';
                el.innerHTML = `<span class="sticker-emoji" style="font-size: 32px;">${s.code}</span><span class="sticker-name">${s.name}</span>`;
                el.onclick = () => sendSticker(s.id, s.code);
                grid.appendChild(el);
            });
        }
    } catch(e) {}
}

// ========== ОТПРАВКА ФАЙЛА ==========
window.sendGroupFile = async function(file) {
    if (!file) return;
    if (!groupSocket?.connected) {
        showToast('❌ Нет подключения', 'error');
        return;
    }
    
    await waitForE2EE();
    
    console.log('📁 Отправка файла:', file.name);
    
    const tempId = 'temp_file_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    pendingTempIds.add(tempId);
    
    addMessageToDOM({
        id: tempId,
        temp_id: tempId,
        text: '',
        sender_id: currentUserId,
        sender_username: currentUsername,
        created_at: new Date().toISOString(),
        is_attachment: true,
        attachment_name: file.name,
        attachment_size: file.size
    });
    
    const reader = new FileReader();
    reader.onload = async (e) => {
        const fileData = e.target.result;
        const attachmentData = JSON.stringify({
            type: 'attachment',
            name: file.name,
            mime: file.type,
            size: file.size,
            data: fileData
        });
        
        let encrypted = attachmentData;
        let iv = null;
        let mac = null;
        
        if (groupE2EE && groupE2EE.ready) {
            try {
                const enc = await groupE2EE.encryptMessage(attachmentData);
                encrypted = enc.encrypted;
                iv = enc.iv;
                mac = enc.mac;
                console.log('🔐 Файл зашифрован');
            } catch(e) {
                console.error('Ошибка шифрования:', e);
                iv = 'plain';
                mac = '';
            }
        } else {
            iv = 'plain';
            mac = '';
        }
        
        groupSocket.emit('send_group_message', {
            group_id: parseInt(groupId),
            encrypted: encrypted,
            iv: iv,
            mac: mac,
            temp_id: tempId,
            is_attachment: true,
            attachment_name: file.name,
            attachment_size: file.size,
            attachment_type: file.type
        });
        
        showToast(`✅ ${file.name} отправлен`, 'success');
    };
    reader.readAsDataURL(file);
};

// ========== СКРЕПКА (ПРЯМОЙ КЛИК) ==========
function initAttachments() {
    console.log('🔧 Настройка скрепки...');
    
    const btn = document.getElementById('groupAttachmentBtn');
    const fileInput = document.getElementById('groupFileInput');
    
    if (!btn) {
        console.error('❌ Кнопка скрепки не найдена');
        return;
    }
    
    if (!fileInput) {
        console.error('❌ fileInput не найден');
        return;
    }
    
    console.log('✅ Кнопка скрепки найдена');
    
    // Прямой клик — сразу открываем выбор файла
    btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('📎 Клик по скрепке');
        fileInput.click();
    };
    
    // Обработчик выбора файла
    fileInput.onchange = (e) => {
        if (e.target.files && e.target.files[0]) {
            console.log('📁 Выбран файл:', e.target.files[0].name);
            window.sendGroupFile(e.target.files[0]);
            fileInput.value = '';
        }
    };
    
    // Скрываем меню
    const menu = document.getElementById('groupAttachmentMenu');
    if (menu) menu.style.display = 'none';
}

// ========== КНОПКИ ==========
function initButtons() {
    const sendBtn = document.getElementById('sendGroupButton');
    const input = document.getElementById('groupMessageInput');
    
    if (sendBtn) sendBtn.onclick = sendText;
    if (input) {
        input.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendText();
            }
        };
        input.oninput = function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
            if (groupSocket?.connected) {
                groupSocket.emit('group_typing', { group_id: parseInt(groupId) });
            }
        };
    }
    
    const stickerBtn = document.getElementById('stickerBtn');
    if (stickerBtn) {
        stickerBtn.onclick = () => {
            const panel = document.getElementById('stickerPanel');
            if (panel) panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
        };
    }
    
    const membersBtn = document.getElementById('membersBtn');
    if (membersBtn) {
        membersBtn.onclick = () => {
            const sidebar = document.getElementById('membersSidebar');
            if (sidebar) sidebar.style.display = sidebar.style.display === 'flex' ? 'none' : 'flex';
        };
    }
    
    const closeSidebar = document.getElementById('closeSidebar');
    if (closeSidebar) {
        closeSidebar.onclick = () => {
            const sidebar = document.getElementById('membersSidebar');
            if (sidebar) sidebar.style.display = 'none';
        };
    }
    
    const inviteBtn = document.getElementById('inviteBtn');
    if (inviteBtn) {
        inviteBtn.onclick = async () => {
            try {
                const res = await fetch(`/groups/${groupId}/invite`);
                const data = await res.json();
                if (data.invite_link) {
                    await navigator.clipboard.writeText(data.invite_link);
                    showToast('🔗 Ссылка скопирована!', 'success');
                }
            } catch(e) {
                showToast('❌ Ошибка', 'error');
            }
        };
    }
    
    const addMemberBtn = document.getElementById('addMemberBtn');
    if (addMemberBtn) {
        addMemberBtn.onclick = () => {
            const username = prompt('Введите имя пользователя:');
            if (username) {
                fetch(`/groups/${groupId}/add-member`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                    body: JSON.stringify({ username: username.trim() })
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        showToast(`✅ ${username} добавлен`, 'success');
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        showToast(`❌ ${data.error}`, 'error');
                    }
                });
            }
        };
    }
}

function getCsrfToken() {
    let token = document.querySelector('meta[name="csrf-token"]');
    if (token) return token.getAttribute('content');
    token = document.querySelector('input[name="csrf_token"]');
    if (token) return token.value;
    return '';
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ==========
function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function scrollToBottom() {
    const area = document.getElementById('groupMessagesArea');
    if (area) setTimeout(() => area.scrollTop = area.scrollHeight, 100);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#333'};
        color: white;
        padding: 12px 20px;
        border-radius: 12px;
        z-index: 10000;
        font-size: 14px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    `;
    toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" style="background:none;border:none;color:white;margin-left:10px;cursor:pointer;">✕</button>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}