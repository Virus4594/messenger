// static/js/e2ee-storage.js
class E2EEStorage {
    constructor() {
        this.dbName = 'e2eeKeys';
        this.storeName = 'privateKeys';
        this.db = null;
    }

    async openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, 1);
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.storeName)) {
                    db.createObjectStore(this.storeName, { keyPath: 'id' });
                }
            };
            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve();
            };
            request.onerror = (event) => reject(event.target.error);
        });
    }

    async savePrivateKey(userId, encryptedKey, iv, salt) {
        await this.openDB();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.storeName, 'readwrite');
            const store = tx.objectStore(this.storeName);
            store.put({ id: `user_${userId}`, encryptedKey, iv, salt });
            tx.oncomplete = resolve;
            tx.onerror = reject;
        });
    }

    async getPrivateKey(userId) {
        await this.openDB();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.storeName, 'readonly');
            const store = tx.objectStore(this.storeName);
            const request = store.get(`user_${userId}`);
            request.onsuccess = () => resolve(request.result);
            request.onerror = reject;
        });
    }

    async deletePrivateKey(userId) {
        await this.openDB();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.storeName, 'readwrite');
            const store = tx.objectStore(this.storeName);
            store.delete(`user_${userId}`);
            tx.oncomplete = resolve;
            tx.onerror = reject;
        });
    }
}