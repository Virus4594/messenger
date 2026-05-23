// E2EE для групповых чатов
class GroupE2EE {
    constructor(groupId, groupEncryptedKeyBase64 = null) {
        this.groupId = groupId;
        this.groupKey = null;
        this.groupEncryptedKey = groupEncryptedKeyBase64;
    }
    
    async init() {
        if (this.groupEncryptedKey) {
            // Расшифровываем групповой ключ личным ключом пользователя
            try {
                const storage = new E2EEStorage();
                const savedData = await storage.getPrivateKey(currentUserId);
                if (savedData) {
                    const password = await this.promptPassword();
                    const privateKeyRaw = await decryptPrivateKey(
                        savedData.encryptedKey, savedData.iv, savedData.salt, password
                    );
                    const privateKey = await crypto.subtle.importKey(
                        "pkcs8", privateKeyRaw,
                        { name: "ECDH", namedCurve: "P-256" },
                        true, ["deriveKey"]
                    );
                    
                    // Расшифровываем групповой ключ
                    const encryptedKeyData = Uint8Array.from(atob(this.groupEncryptedKey), c => c.charCodeAt(0));
                    const groupKeyRaw = await crypto.subtle.decrypt(
                        { name: "RSA-OAEP" }, privateKey, encryptedKeyData
                    );
                    this.groupKey = await crypto.subtle.importKey(
                        "raw", groupKeyRaw,
                        { name: "AES-GCM", length: 256 },
                        true, ["encrypt", "decrypt"]
                    );
                }
            } catch(e) {
                console.error('Failed to decrypt group key:', e);
            }
        }
        return this.groupKey !== null;
    }
    
    async encryptMessage(text) {
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            this.groupKey,
            data
        );
        return {
            encrypted: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
            iv: btoa(String.fromCharCode(...iv))
        };
    }
    
    async decryptMessage(encryptedBase64, ivBase64) {
        if (!this.groupKey) return '🔒 Ключ не найден';
        try {
            const encrypted = Uint8Array.from(atob(encryptedBase64), c => c.charCodeAt(0));
            const iv = Uint8Array.from(atob(ivBase64), c => c.charCodeAt(0));
            const decrypted = await crypto.subtle.decrypt(
                { name: "AES-GCM", iv: iv },
                this.groupKey,
                encrypted
            );
            return new TextDecoder().decode(decrypted);
        } catch(e) {
            return '🔒 Не удалось расшифровать';
        }
    }
    
    promptPassword() {
        return new Promise((resolve) => {
            const password = prompt('Введите пароль для расшифровки ключей группы:');
            resolve(password);
        });
    }
}