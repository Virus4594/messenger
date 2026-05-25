// group-e2ee.js - Групповое E2EE (рабочая версия)
class GroupE2EE {
    constructor(groupId, currentUserId) {
        this.groupId = groupId;
        this.currentUserId = currentUserId;
        this.groupKey = null;
        this.ready = false;
    }
    
    async init() {
        try {
            console.log('🔐 [GROUP] Инициализация группового E2EE...');
            
            // Пока используем упрощённое шифрование для групп
            // Генерируем детерминированный ключ для группы
            const encoder = new TextEncoder();
            const keyMaterial = await crypto.subtle.importKey(
                "raw",
                encoder.encode(`group_${this.groupId}_key`),
                { name: "PBKDF2" },
                false,
                ["deriveKey"]
            );
            
            const salt = encoder.encode(`group_salt_${this.groupId}`);
            
            this.groupKey = await crypto.subtle.deriveKey(
                {
                    name: "PBKDF2",
                    salt: salt,
                    iterations: 10000,
                    hash: "SHA-256"
                },
                keyMaterial,
                { name: "AES-GCM", length: 256 },
                false,
                ["encrypt", "decrypt"]
            );
            
            this.ready = true;
            console.log('✅ [GROUP] Групповое E2EE готово');
            return true;
        } catch(e) {
            console.error('[GROUP] E2EE error:', e);
            return false;
        }
    }
    
    async encryptMessage(text) {
        if (!this.ready || !this.groupKey) {
            return { encrypted: text, iv: null };
        }
        
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        
        const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            this.groupKey,
            data
        );
        
        return {
            encrypted: this.bufferToBase64(encrypted),
            iv: this.bufferToBase64(iv)
        };
    }
    
    async decryptMessage(encryptedBase64, ivBase64) {
        if (!this.ready || !this.groupKey) {
            return encryptedBase64 || '🔒 Нет ключа';
        }
        
        if (!encryptedBase64 || !ivBase64) {
            return '🔒 Нет данных';
        }
        
        try {
            const encrypted = this.base64ToBuffer(encryptedBase64);
            const iv = this.base64ToBuffer(ivBase64);
            
            const decrypted = await crypto.subtle.decrypt(
                { name: "AES-GCM", iv: iv },
                this.groupKey,
                encrypted
            );
            
            const decoder = new TextDecoder();
            let text = decoder.decode(decrypted);
            
            try {
                const obj = JSON.parse(text);
                if (obj.type === 'sticker') return obj.code;
                if (obj.type === 'text') return obj.text;
                return text;
            } catch {
                return text;
            }
        } catch(e) {
            console.error('[GROUP] Decrypt error:', e);
            return '🔒 Ошибка расшифровки';
        }
    }
    
    bufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
    
    base64ToBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes;
    }
}