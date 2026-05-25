let groupChat = { socket: null, e2ee: null, groupId: null, currentUserId: null };

async function initGroupChat() {
    groupChat.groupId = document.getElementById('groupId')?.value;
    groupChat.currentUserId = document.getElementById('currentUserId')?.value;
    
    if (!groupChat.groupId) return;
    
    groupChat.e2ee = new GroupE2EEModule(groupChat.groupId, groupChat.currentUserId, '');
    await groupChat.e2ee.init();
    
    groupChat.socket = io();
    groupChat.socket.on('connect', () => {
        groupChat.socket.emit('join_group', { group_id: parseInt(groupChat.groupId) });
    });
    
    groupChat.socket.on('new_group_message', async (data) => {
        let text = data.encrypted;
        if (groupChat.e2ee.ready && data.encrypted && data.iv) {
            text = await groupChat.e2ee.decryptMessage(data.encrypted, data.iv);
        }
        const container = document.getElementById('groupMessagesList');
        if (container) {
            container.innerHTML += `<div class="message"><b>${data.sender_username}:</b> ${text}</div>`;
            container.scrollTop = container.scrollHeight;
        }
    });
    
    document.getElementById('sendGroupButton')?.addEventListener('click', sendGroupMessage);
    document.getElementById('groupMessageInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendGroupMessage();
    });
}

async function sendGroupMessage() {
    const input = document.getElementById('groupMessageInput');
    const text = input?.value.trim();
    if (!text) return;
    input.value = '';
    
    let encrypted = text, iv = null;
    if (groupChat.e2ee?.ready) {
        const enc = await groupChat.e2ee.encryptMessage(text);
        encrypted = enc.encrypted;
        iv = enc.iv;
    }
    groupChat.socket?.emit('send_group_message', {
        group_id: parseInt(groupChat.groupId),
        encrypted: encrypted, iv: iv
    });
}

document.addEventListener('DOMContentLoaded', initGroupChat);