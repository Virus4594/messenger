// groups-chat.js - упрощенная версия без E2EE
let groupSocket = null;
let currentGroupId = null;
let currentUserId = null;
let currentUserRole = null;
let pollingInterval = null;

async function initGroupChat() {
    console.log('🚀 Инициализация группового чата (режим без E2EE)');
    
    currentGroupId = document.getElementById('groupId')?.value;
    currentUserId = document.getElementById('currentUserId')?.value;
    currentUserRole = document.getElementById('currentUserRole')?.value;
    
    if (!currentGroupId || !currentUserId) {
        console.error('❌ Не найдены данные группы');
        return;
    }
    
    // Загружаем сообщения
    await loadGroupMessages();
    
    // Настраиваем WebSocket
    setupGroupSocket();
    
    // Настраиваем обработчики событий
    setupGroupEventListeners();
    
    // Запускаем polling как fallback
    startPolling();
    
    console.log('✅ Групповой чат инициализирован');
}

function setupGroupSocket() {
    if (typeof io !== 'undefined') {
        groupSocket = io();
        
        groupSocket.on('connect', () => {
            console.log('✅ WebSocket подключен');
            groupSocket.emit('join_group', { group_id: currentGroupId });
        });
        
        groupSocket.on('new_group_message', (data) => {
            console.log('📨 Новое сообщение:', data);
            if (data.sender_id != currentUserId) {
                displayGroupMessage(
                    data.sender_username,
                    data.text,
                    data.created_at,
                    false,
                    data.is_sticker,
                    data.sticker_code
                );
            }
        });
        
        groupSocket.on('group_typing', (data) => {
            showTypingIndicator(data.sender_username);
        });
        
        groupSocket.on('connect_error', (error) => {
            console.warn('⚠️ WebSocket ошибка:', error);
        });
    } else {
        console.warn('⚠️ Socket.IO не загружен, используем только polling');
    }
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    
    pollingInterval = setInterval(async () => {
        await loadGroupMessages(true); // true = только новые сообщения
    }, 5000);
}

async function loadGroupMessages(onlyNew = false) {
    try {
        const response = await fetch(`/api/group-messages/${currentGroupId}`);
        const data = await response.json();
        
        if (!data.messages || data.messages.length === 0) {
            if (!onlyNew) {
                const container = document.getElementById('groupMessagesList');
                if (container && container.children.length === 0) {
                    container.innerHTML = '<div class="empty-chat">💬 Напишите первое сообщение!</div>';
                }
            }
            return;
        }
        
        const lastMessageId = localStorage.getItem(`group_last_id_${currentGroupId}`) || 0;
        
        if (onlyNew) {
            // Показываем только новые сообщения
            const newMessages = data.messages.filter(m => m.id > lastMessageId);
            for (const msg of newMessages) {
                if (msg.sender_id != currentUserId) {
                    displayGroupMessage(
                        msg.sender_username,
                        msg.text,
                        msg.created_at,
                        false,
                        false,
                        null
                    );
                }
            }
            if (newMessages.length > 0) {
                localStorage.setItem(`group_last_id_${currentGroupId}`, data.messages[data.messages.length - 1].id);
            }
        } else {
            // Полная перезагрузка
            const container = document.getElementById('groupMessagesList');
            if (!container) return;
            
            container.innerHTML = '';
            
            for (const msg of data.messages) {
                displayGroupMessage(
                    msg.sender_username,
                    msg.text,
                    msg.created_at,
                    msg.sender_id == currentUserId,
                    false,
                    null
                );
            }
            
            if (data.messages.length > 0) {
                localStorage.setItem(`group_last_id_${currentGroupId}`, data.messages[data.messages.length - 1].id);
            }
            
            scrollToBottom();
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки сообщений:', error);
    }
}

function displayGroupMessage(username, text, timestamp, isMine, isSticker, stickerCode) {
    const container = document.getElementById('groupMessagesList');
    if (!container) return;
    
    // Убираем заглушку "нет сообщений"
    const emptyDiv = container.querySelector('.empty-chat');
    if (emptyDiv) emptyDiv.remove();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `group-message ${isMine ? 'sent' : 'received'}`;
    
    const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const date = new Date(timestamp).toLocaleDateString();
    
    let contentHtml = '';
    if (isSticker && stickerCode) {
        contentHtml = `<div class="sticker-emoji" style="font-size: 48px;">${stickerCode}</div>`;
    } else {
        contentHtml = `<div class="message-text">${escapeHtml(text || '...')}</div>`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${escapeHtml(username.charAt(0).toUpperCase())}</div>
        <div class="message-bubble">
            <div class="message-sender">${escapeHtml(username)}</div>
            ${contentHtml}
            <div class="message-time">${time} <span class="message-date">${date}</span></div>
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
    
    // Показываем временное сообщение
    displayGroupMessage(
        document.getElementById('currentUsername')?.value || 'Вы',
        text,
        new Date().toISOString(),
        true,
        false,
        null
    );
    
    try {
        const response = await fetch('/api/group-messages/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                group_id: currentGroupId,
                text: text,
                is_sticker: false
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            console.error('Send error:', data.error);
            alert('Ошибка отправки: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Network error:', error);
        alert('Ошибка сети. Попробуйте еще раз.');
    }
}

function setupGroupEventListeners() {
    const sendBtn = document.getElementById('sendGroupButton');
    const input = document.getElementById('groupMessageInput');
    const membersBtn = document.getElementById('membersBtn');
    const closeSidebar = document.getElementById('closeSidebar');
    const stickerBtn = document.getElementById('stickerBtn');
    const stickerPanel = document.getElementById('stickerPanel');
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendGroupMessage);
    }
    
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendGroupMessage();
            }
        });
        
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
            
            if (groupSocket && groupSocket.connected) {
                groupSocket.emit('group_typing', { group_id: currentGroupId });
            }
        });
    }
    
    if (membersBtn) {
        membersBtn.addEventListener('click', toggleMembersSidebar);
    }
    
    if (closeSidebar) {
        closeSidebar.addEventListener('click', () => {
            const sidebar = document.getElementById('membersSidebar');
            if (sidebar) sidebar.style.display = 'none';
        });
    }
    
    if (stickerBtn && stickerPanel) {
        stickerBtn.addEventListener('click', () => {
            const isVisible = stickerPanel.style.display === 'flex';
            stickerPanel.style.display = isVisible ? 'none' : 'flex';
        });
        
        // Загружаем стикеры
        loadStickers();
    }
    
    // Закрыть стикер-панель при клике вне
    document.addEventListener('click', (e) => {
        if (stickerPanel && !stickerPanel.contains(e.target) && e.target !== stickerBtn) {
            stickerPanel.style.display = 'none';
        }
    });
}

async function loadStickers() {
    try {
        const response = await fetch('/api/stickers');
        const stickers = await response.json();
        
        const stickerGrid = document.querySelector('.sticker-grid');
        if (!stickerGrid) return;
        
        stickerGrid.innerHTML = '';
        
        stickers.forEach(sticker => {
            const stickerEl = document.createElement('div');
            stickerEl.className = 'sticker-item';
            stickerEl.innerHTML = `<span class="sticker-emoji">${sticker.code}</span><span class="sticker-name">${sticker.name}</span>`;
            stickerEl.onclick = () => sendSticker(sticker.code);
            stickerGrid.appendChild(stickerEl);
        });
    } catch (error) {
        console.error('Ошибка загрузки стикеров:', error);
    }
}

async function sendSticker(stickerCode) {
    const stickerPanel = document.getElementById('stickerPanel');
    if (stickerPanel) stickerPanel.style.display = 'none';
    
    try {
        const response = await fetch('/api/group-messages/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                group_id: currentGroupId,
                text: stickerCode,
                is_sticker: true,
                sticker_code: stickerCode
            })
        });
        
        const data = await response.json();
        if (data.success) {
            displayGroupMessage(
                document.getElementById('currentUsername')?.value || 'Вы',
                stickerCode,
                new Date().toISOString(),
                true,
                true,
                stickerCode
            );
        }
    } catch (error) {
        console.error('Sticker send error:', error);
    }
}

function toggleMembersSidebar() {
    const sidebar = document.getElementById('membersSidebar');
    if (!sidebar) return;
    
    if (sidebar.style.display === 'none' || !sidebar.style.display) {
        sidebar.style.display = 'flex';
        loadMembersList();
    } else {
        sidebar.style.display = 'none';
    }
}

async function loadMembersList() {
    try {
        const response = await fetch(`/api/group/${currentGroupId}/members`);
        const data = await response.json();
        
        const membersList = document.getElementById('membersList');
        const memberCountSpan = document.getElementById('sidebarMemberCount');
        
        if (!membersList) return;
        
        if (memberCountSpan) {
            memberCountSpan.textContent = data.members.length;
        }
        
        membersList.innerHTML = '';
        
        for (const member of data.members) {
            const memberDiv = document.createElement('div');
            memberDiv.className = 'member-item';
            memberDiv.dataset.userId = member.id;
            
            memberDiv.innerHTML = `
                <div class="member-avatar">${escapeHtml(member.username.charAt(0).toUpperCase())}</div>
                <div class="member-info">
                    <span class="member-name">${escapeHtml(member.username)}</span>
                    <span class="member-role-badge ${member.role}">${member.role === 'admin' ? 'Админ' : 'Участник'}</span>
                </div>
                <div class="member-status ${member.is_online ? 'online' : 'offline'}"></div>
                ${currentUserRole === 'admin' && member.id != currentUserId ? `<button class="remove-member-btn" data-user-id="${member.id}" data-username="${escapeHtml(member.username)}">🗑️</button>` : ''}
            `;
            
            membersList.appendChild(memberDiv);
        }
        
        // Добавляем обработчики для кнопок удаления
        document.querySelectorAll('.remove-member-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const userId = btn.dataset.userId;
                const username = btn.dataset.username;
                
                if (confirm(`Удалить ${username} из группы?`)) {
                    await removeMember(userId);
                }
            });
        });
        
    } catch (error) {
        console.error('Error loading members:', error);
    }
}

async function removeMember(userId) {
    try {
        const response = await fetch(`/groups/${currentGroupId}/remove-member`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ user_id: userId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            await loadMembersList();
            // Обновляем счетчик участников в шапке
            const memberCountSpan = document.getElementById('memberCount');
            if (memberCountSpan) {
                const currentCount = parseInt(memberCountSpan.textContent);
                memberCountSpan.textContent = currentCount - 1;
            }
        } else {
            alert('Ошибка: ' + (data.error || 'Не удалось удалить участника'));
        }
    } catch (error) {
        console.error('Remove member error:', error);
        alert('Ошибка при удалении участника');
    }
}

function showTypingIndicator(username) {
    const indicator = document.getElementById('groupTypingIndicator');
    const usernameSpan = document.getElementById('groupTypingUsername');
    
    if (indicator && usernameSpan) {
        usernameSpan.textContent = username;
        indicator.style.display = 'flex';
        
        clearTimeout(window.typingTimeout);
        window.typingTimeout = setTimeout(() => {
            indicator.style.display = 'none';
        }, 3000);
    }
}

function scrollToBottom() {
    const area = document.getElementById('groupMessagesArea');
    if (area) {
        setTimeout(() => {
            area.scrollTop = area.scrollHeight;
        }, 100);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCsrfToken() {
    let token = document.querySelector('meta[name="csrf-token"]');
    if (token) return token.getAttribute('content');
    token = document.querySelector('input[name="csrf_token"]');
    if (token) return token.value;
    return '';
}

// Запускаем при загрузке
document.addEventListener('DOMContentLoaded', () => {
    // Даем время на загрузку остальных скриптов
    setTimeout(initGroupChat, 500);
});

window.initGroupChat = initGroupChat;