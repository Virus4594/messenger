// static/js/chat.js

class SimpleChat {
    constructor(options) {
        this.currentUserId = options.currentUserId;
        this.currentUsername = options.currentUsername;
        this.otherUserId = options.otherUserId;
        this.otherUsername = options.otherUsername;
        this.socket = null;
        this.processedIds = new Set();
        this.typingTimeout = null;
        
        this.init();
    }
    
    init() {
        this.connectSocket();
        this.loadHistory();
        this.setupEvents();
        this.requestNotificationPermission();
    }
    
    connectSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('✅ WebSocket подключен');
            this.updateConnectionStatus(true);
            this.socket.emit('join_chat', { other_user_id: this.otherUserId });
        });
        
        this.socket.on('disconnect', () => {
            console.log('❌ WebSocket отключен');
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('new_message', (data) => {
            if (!this.processedIds.has(data.id)) {
                this.processedIds.add(data.id);
                this.displayMessage(data, data.sender_id === this.currentUserId);
                this.scrollToBottom();
                
                // Уведомление и звук для чужих сообщений
                if (data.sender_id !== this.currentUserId) {
                    this.playSound();
                    this.showNotification(data);
                }
            }
        });
        
        this.socket.on('user_typing', (data) => {
            if (data.sender_id === this.otherUserId) {
                this.showTyping(data.sender_username);
            }
        });
        
        this.socket.on('error', (data) => {
            this.showToast(data.message, 'error');
        });
    }
    
    async loadHistory() {
        try {
            const res = await fetch(`/api/messages/${this.otherUserId}`);
            const data = await res.json();
            
            const container = document.getElementById('chatMessagesList');
            if (!container) return;
            
            container.innerHTML = '';
            this.processedIds.clear();
            
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    this.processedIds.add(msg.id);
                    this.displayMessage(msg, msg.sender_id === this.currentUserId);
                });
            } else {
                container.innerHTML = `
                    <div class="chat-empty">
                        <div class="chat-empty-icon">💬</div>
                        <p>Напишите первое сообщение!</p>
                    </div>
                `;
            }
            this.scrollToBottom();
        } catch (error) {
            console.error('Ошибка:', error);
        }
    }
    
    displayMessage(msg, isMine) {
        const container = document.getElementById('chatMessagesList');
        if (!container) return;
        
        // Убираем пустое состояние
        const empty = container.querySelector('.chat-empty');
        if (empty) empty.remove();
        
        // Проверка дубликата
        if (document.querySelector(`.chat-message[data-id="${msg.id}"]`)) return;
        
        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${isMine ? 'sent' : 'received'}`;
        messageEl.setAttribute('data-id', msg.id);
        
        const time = new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        if (isMine) {
            messageEl.innerHTML = `
                <div class="message-bubble">
                    <div class="message-text">${this.escapeHtml(msg.text)}</div>
                    <div class="message-time">${time} ✓</div>
                </div>
            `;
        } else {
            messageEl.innerHTML = `
                <div class="message-bubble">
                    <div class="message-author">${this.escapeHtml(msg.sender_username)}</div>
                    <div class="message-text">${this.escapeHtml(msg.text)}</div>
                    <div class="message-time">${time}</div>
                </div>
            `;
        }
        
        container.appendChild(messageEl);
    }
    
    sendMessage() {
        const input = document.getElementById('chatInput');
        const text = input.value.trim();
        if (!text) return;
        
        input.value = '';
        input.style.height = 'auto';
        
        // Временное сообщение
        const tempId = 'temp_' + Date.now();
        const tempMsg = {
            id: tempId,
            text: text,
            sender_id: this.currentUserId,
            sender_username: this.currentUsername,
            created_at: new Date().toISOString()
        };
        
        this.processedIds.add(tempId);
        this.displayMessage(tempMsg, true);
        this.scrollToBottom();
        
        // Отправляем
        this.socket.emit('send_message', {
            text: text,
            receiver_id: this.otherUserId
        });
    }
    
    sendTyping() {
        if (this.socket) {
            this.socket.emit('typing', { receiver_id: this.otherUserId });
            clearTimeout(this.typingTimeout);
            this.typingTimeout = setTimeout(() => {}, 2000);
        }
    }
    
    showTyping(username) {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.innerHTML = `
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
                <span>${username} печатает...</span>
            `;
            indicator.classList.add('active');
            
            setTimeout(() => {
                indicator.classList.remove('active');
            }, 3000);
        }
    }
    
    updateConnectionStatus(connected) {
        const status = document.getElementById('connectionStatus');
        if (status) {
            status.className = `connection-status ${connected ? 'online' : 'offline'}`;
            status.title = connected ? 'Соединение есть' : 'Нет соединения';
        }
    }
    
    playSound() {
        try {
            const audio = new Audio();
            // Используем Web Audio API
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            const ctx = new AudioContext();
            const oscillator = ctx.createOscillator();
            const gain = ctx.createGain();
            oscillator.connect(gain);
            gain.connect(ctx.destination);
            oscillator.frequency.value = 880;
            gain.gain.value = 0.1;
            oscillator.start();
            gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.3);
            oscillator.stop(ctx.currentTime + 0.3);
            if (ctx.state === 'suspended') ctx.resume();
        } catch(e) {}
    }
    
    showNotification(data) {
        // Звук
        this.playSound();
        
        // Toast уведомление
        this.showToast(`📨 ${data.sender_username}: ${data.text.substring(0, 50)}`, 'info');
        
        // Браузерное уведомление
        if (Notification.permission === 'granted' && document.hidden) {
            new Notification(`${data.sender_username}`, {
                body: data.text.length > 60 ? data.text.substring(0, 60) + '...' : data.text,
                icon: '/static/favicon.ico',
                silent: true
            });
        }
    }
    
    showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `chat-toast ${type}`;
        toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()">×</button>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
    
    requestNotificationPermission() {
        if (Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
    
    scrollToBottom() {
        const area = document.getElementById('chatMessagesArea');
        if (area) area.scrollTop = area.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    setupEvents() {
        const input = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        
        if (sendBtn) {
            sendBtn.onclick = () => this.sendMessage();
        }
        
        if (input) {
            input.onkeydown = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            };
            
            input.oninput = (e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
                this.sendTyping();
            };
        }
    }
}