// group-e2ee.js - Групповое E2EE с HMAC (ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ)

class GroupE2EE {
    constructor(groupId, currentUserId) {
        this.groupId = groupId;
        this.currentUserId = currentUserId;
        this.groupKey = null;
        this.hmacKey = null;
        this.ready = false;
        this.keyVersion = null;
    }
    
    async init() {
        try {
            console.log('🔐 [GROUP] Инициализация группового E2EE...');
            
            const response = await fetch(`/api/group/${this.groupId}/key`);
            if (!response.ok) {
                console.error('❌ Не удалось получить ключ группы:', response.status);
                return false;
            }
            
            const data = await response.json();
            
            if (!data.group_key) {
                console.error('❌ Нет ключа в ответе');
                return false;
            }
            
            const keyData = this.base64ToBuffer(data.group_key);
            
            const rawKeyMaterial = await crypto.subtle.importKey(
                "raw",
                keyData,
                { name: "HKDF" },
                false,
                ["deriveKey"]
            );
            
            this.groupKey = await crypto.subtle.deriveKey(
                {
                    name: "HKDF",
                    hash: "SHA-256",
                    salt: this.stringToBuffer("aes_salt"),
                    info: this.stringToBuffer("aes_info")
                },
                rawKeyMaterial,
                { name: "AES-GCM", length: 256 },
                false,
                ["encrypt", "decrypt"]
            );
            
            this.hmacKey = await crypto.subtle.deriveKey(
                {
                    name: "HKDF",
                    hash: "SHA-256",
                    salt: this.stringToBuffer("hmac_salt"),
                    info: this.stringToBuffer("hmac_info")
                },
                rawKeyMaterial,
                { name: "HMAC", hash: "SHA-256" },
                false,
                ["sign", "verify"]
            );
            
            this.keyVersion = data.key_version || "1.0";
            this.ready = true;
            console.log('✅ [GROUP] Групповое E2EE готово (V' + this.keyVersion + ')');
            return true;
        } catch(e) {
            console.error('[GROUP] E2EE init error:', e);
            return false;
        }
    }
    
        async encryptMessage(text) {
        if (!this.ready || !this.groupKey) {
            console.warn('⚠️ E2EE не готов, возвращаем plain text');
            return { encrypted: text, iv: 'plain', mac: '' };
        }
        
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        
        const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            this.groupKey,
            data
        );
        
        const toSign = new Uint8Array([...iv, ...new Uint8Array(encrypted)]);
        const mac = await crypto.subtle.sign("HMAC", this.hmacKey, toSign);
        
        return {
            encrypted: this.bufferToBase64(encrypted),
            iv: this.bufferToBase64(iv),
            mac: this.bufferToBase64(mac),
            key_version: this.keyVersion
        };
    }
    
    async decryptMessage(encryptedBase64, ivBase64, macBase64) {
    // Если iv === 'plain' - сообщение не зашифровано
    if (ivBase64 === 'plain') {
        try {
            return JSON.parse(encryptedBase64);
        } catch(e) {
            return encryptedBase64;
        }
    }
    
    if (!this.ready || !this.groupKey) {
        return encryptedBase64 || '🔒 Нет ключа';
    }
    
    if (!encryptedBase64 || !ivBase64 || !macBase64) {
        return '🔒 Нет данных шифрования';
    }
        
        try {
            const encrypted = this.base64ToBuffer(encryptedBase64);
            const iv = this.base64ToBuffer(ivBase64);
            const mac = this.base64ToBuffer(macBase64);
            
            const toVerify = new Uint8Array([...iv, ...new Uint8Array(encrypted)]);
            const isValid = await crypto.subtle.verify("HMAC", this.hmacKey, mac, toVerify);
            
            if (!isValid) {
                console.error('❌ Ошибка целостности сообщения!');
                return '🔒 ОШИБКА ЦЕЛОСТНОСТИ';
            }
            
            const decrypted = await crypto.subtle.decrypt(
                { name: "AES-GCM", iv: iv },
                this.groupKey,
                encrypted
            );
            
            const decoder = new TextDecoder();
            let text = decoder.decode(decrypted);
            
            try {
                const obj = JSON.parse(text);
                if (obj.type === 'sticker') return { type: 'sticker', code: obj.code };
                if (obj.type === 'text') return obj.text;
                if (obj.type === 'attachment') return obj;
                return obj;
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
    
    stringToBuffer(str) {
        const encoder = new TextEncoder();
        return encoder.encode(str);
    }
}