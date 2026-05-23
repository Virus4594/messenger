// Групповой чат
let groupSocket = null;
let groupE2EE = null;
let currentGroupId = parseInt(document.getElementById('groupId')?.value);
let currentUserRole = document.getElementById('currentUserRole')?.value;

async function initGroupChat() {
    if (!currentGroupId) return;
    
    // Инициализация WebSocket
    groupSocket = io({ transports: ['websocket', 'polling'] });
    
    groupSocket.on('connect', () => {
        console.log('✅ Group WebSocket connected');
        groupSocket.emit('join_group', { group_id: currentGroupId });
    });
    
    // Инициализация E2EE
    const encryptedKey = document.getElementById('groupEncryptedKey')?.value;
    groupE2EE = new GroupE2EE(currentGroupId, encryptedKey);
    const e2eeReady = await groupE2EE.init();
    
    if (e2eeReady) {
        document.getElementById('sendGroupButton').disabled = false;
        document.getElementById('groupMessageInput').disabled = false;
    }
    
    // Загрузка истории
    await loadGroupHistory();
    
    // Обработка новых сообщений
    groupSocket.on('new_group_message', async (data) => {
        const decrypted = await groupE2EE.decryptMessage(data.encrypted, data.iv);
        displayGroupMessage({
            id: data.id,
            text: decrypted,
            sender_id: data.sender_id,
            sender_username: data.sender_username,
            created_at: data.created_at,
            is_mine: data.sender_id === currentUserId
        });
    });
    
    groupSocket.on('group_typing', (data) => {
        if (data.sender_id !== currentUserId) {
            const indicator = document.getElementById('groupTypingIndicator');
            const usernameSpan = document.getElementById('groupTypingUsername');
            usernameSpan.textContent = data.sender_username;
            indicator.style.display = 'flex';
            setTimeout(() => indicator.style.display = 'none', 2000);
        }
    });
}

async function loadGroupHistory() {
    try {
        const response = await fetch(`/api/group-messages/${currentGroupId}`);
        const data = await response.json();
        
        const container = document.getElementById('groupMessagesList');
        container.innerHTML = '';
        
        for (const msg of data.messages) {
            const decrypted = await groupE2EE.decryptMessage(msg.encrypted, msg.nonce);
            displayGroupMessage({
                id: msg.id,
                text: decrypted,
                sender_id: msg.sender_id,
                sender_username: msg.sender_username,
                created_at: msg.created_at,
                is_mine: msg.sender_id === currentUserId
            });
        }
        
        scrollToBottom();
    } catch(e) {
        console.error('Load history error:', e);
    }
}

async function sendGroupMessage() {
    const input = document.getElementById('groupMessageInput');
    const text = input.value.trim();
    if (!text || !groupE2EE?.groupKey) return;
    
    input.value = '';
    input.style.height = 'auto';
    
    const encrypted = await groupE2EE.encryptMessage(text);
    
    groupSocket.emit('send_group_message', {
        group_id: currentGroupId,
        encrypted: encrypted.encrypted,
        iv: encrypted.iv
    });
    
    // Показываем временное сообщение
    displayGroupMessage({
        id: 'temp_' + Date.now(),
        text: text,
        sender_id: currentUserId,
        sender_username: currentUsername,
        created_at: new Date().toISOString(),
        is_mine: true,
        is_temp: true
    });
}

function displayGroupMessage(msg) {
    const container = document.getElementById('groupMessagesList');
    const isMine = msg.is_mine;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `group-message ${isMine ? 'sent' : 'received'}`;
    if (msg.id && !msg.id.toString().startsWith('temp')) {
        messageDiv.setAttribute('data-id', msg.id);
    }
    
    const time = new Date(msg.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${msg.sender_username?.charAt(0).toUpperCase() || '?'}</div>
        <div class="message-bubble">
            ${!isMine ? `<div class="message-sender">${escapeHtml(msg.sender_username)}</div>` : ''}
            <div class="message-text">${escapeHtml(msg.text)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    scrollToBottom();
}

function scrollToBottom() {
    const area = document.getElementById('groupMessagesArea');
    if (area) setTimeout(() => area.scrollTop = area.scrollHeight, 100);
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    if (currentGroupId) {
        initGroupChat();
        
        // Отправка сообщения
        const sendBtn = document.getElementById('sendGroupButton');
        const input = document.getElementById('groupMessageInput');
        
        sendBtn.onclick = sendGroupMessage;
        input.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendGroupMessage();
            }
        };
        
        // Индикатор печатания
        let typingTimer;
        input.oninput = () => {
            if (typingTimer) clearTimeout(typingTimer);
            groupSocket?.emit('group_typing', { group_id: currentGroupId });
            typingTimer = setTimeout(() => {}, 2000);
        };
        
        // Боковая панель участников
        const membersBtn = document.getElementById('membersBtn');
        const sidebar = document.getElementById('membersSidebar');
        const closeSidebar = document.getElementById('closeSidebar');
        
        if (membersBtn) {
            membersBtn.onclick = () => {
                sidebar.style.display = 'flex';
            };
        }
        if (closeSidebar) {
            closeSidebar.onclick = () => {
                sidebar.style.display = 'none';
            };
        }
        
        // Приглашение (админ)
        const inviteBtn = document.getElementById('inviteBtn');
        if (inviteBtn) {
            inviteBtn.onclick = async () => {
                const response = await fetch(`/groups/${currentGroupId}/invite`);
                const data = await response.json();
                if (data.invite_link) {
                    prompt('Скопируйте ссылку-приглашение:', data.invite_link);
                } else {
                    alert('Ошибка: ' + data.error);
                }
            };
        }
        
        // Удаление участников
        document.querySelectorAll('.remove-member-btn').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                const userId = btn.dataset.userId;
                const username = btn.dataset.username;
                if (confirm(`Удалить ${username} из группы?`)) {
                    const response = await fetch(`/groups/${currentGroupId}/remove-member`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: parseInt(userId) })
                    });
                    const data = await response.json();
                    if (data.success) {
                        location.reload();
                    } else {
                        alert(data.error);
                    }
                }
            };
        });
    }
});