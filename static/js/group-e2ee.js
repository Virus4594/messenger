// group-e2ee.js - Групповое E2EE (ЗАЩИЩЁННАЯ версия с HMAC)
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
            
            // ИСПРАВКА: Получаем реальный ключ с бэкенда вместо детерминированного
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
            
            // Декодируем ключ (он приходит в base64)
            const keyData = this.base64ToBuffer(data.group_key);
            
            // Сначала импортируем как сырой материал для дальнейшего использования
            const rawKeyMaterial = await crypto.subtle.importKey(
                "raw",
                keyData,
                { name: "HKDF" },  // Используем HKDF для импорта (он универсален)
                false,
                ["deriveKey"]
            );
            
            // Теперь из raw материала создаём ключ для AES-GCM
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
            
            // И ключ для HMAC
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
            return { encrypted: text, iv: null, mac: null };
        }
        
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        
        // Шифруем сообщение
        const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            this.groupKey,
            data
        );
        
        // Вычисляем HMAC для целостности (шифр + IV)
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
            
            // ПРОВЕРЯЕМ ЦЕЛОСТНОСТЬ: HMAC должен совпадать
            const toVerify = new Uint8Array([...iv, ...new Uint8Array(encrypted)]);
            const isValid = await crypto.subtle.verify("HMAC", this.hmacKey, mac, toVerify);
            
            if (!isValid) {
                console.error('❌ Ошибка целостности сообщения! Возможна попытка подделки!');
                return '🔒 ОШИБКА ЦЕЛОСТНОСТИ - Сообщение повреждено или подделано!';
            }
            
            // Расшифровываем
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
    
    stringToBuffer(str) {
        const encoder = new TextEncoder();
        return encoder.encode(str);
    }
}