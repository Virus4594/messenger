class GroupE2EEModule {
    constructor(groupId, currentUserId, currentUsername) {
        this.groupId = groupId;
        this.currentUserId = currentUserId;
        this.groupKey = null;
        this.ready = false;
    }
    
    async init() {
        const encoder = new TextEncoder();
        const keyMaterial = await crypto.subtle.importKey(
            "raw",
            encoder.encode(`group_${this.groupId}_key`),
            { name: "PBKDF2" }, false, ["deriveKey"]
        );
        const salt = encoder.encode(`group_salt_${this.groupId}`);
        this.groupKey = await crypto.subtle.deriveKey(
            { name: "PBKDF2", salt: salt, iterations: 10000, hash: "SHA-256" },
            keyMaterial,
            { name: "AES-GCM", length: 256 },
            false, ["encrypt", "decrypt"]
        );
        this.ready = true;
        return true;
    }
    
    async encryptMessage(text) {
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv }, this.groupKey, data
        );
        return { 
            encrypted: btoa(String.fromCharCode(...new Uint8Array(encrypted))), 
            iv: btoa(String.fromCharCode(...iv)) 
        };
    }
    
    async decryptMessage(encryptedBase64, ivBase64) {
        if (!encryptedBase64 || !ivBase64) return '🔒 Нет данных';
        try {
            const encrypted = Uint8Array.from(atob(encryptedBase64), c => c.charCodeAt(0));
            const iv = Uint8Array.from(atob(ivBase64), c => c.charCodeAt(0));
            const decrypted = await crypto.subtle.decrypt(
                { name: "AES-GCM", iv: iv }, this.groupKey, encrypted
            );
            return new TextDecoder().decode(decrypted);
        } catch(e) { 
            return '🔒 Ошибка расшифровки'; 
        }
    }
}