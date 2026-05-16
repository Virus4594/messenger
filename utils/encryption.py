import base64
import hashlib
import secrets
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import json

class E2EEncryption:
    """End-to-End шифрование для мессенджера"""
    
    @staticmethod
    def generate_key_pair(password: str, salt: bytes = None) -> dict:
        """Генерация пары ключей RSA"""
        if salt is None:
            salt = get_random_bytes(32)
        
        # Генерируем RSA ключи (2048 бит)
        key = RSA.generate(2048)
        private_key = key.export_key('PEM')
        public_key = key.publickey().export_key('PEM')
        
        # Шифруем приватный ключ паролем пользователя
        encrypted_private = E2EEncryption._encrypt_with_password(
            private_key.decode(), password, salt
        )
        
        return {
            'public_key': public_key.decode(),
            'encrypted_private_key': encrypted_private,
            'salt': base64.b64encode(salt).decode(),
            'fingerprint': E2EEncryption.get_key_fingerprint(public_key.decode())
        }
    
    @staticmethod
    def _encrypt_with_password(data: str, password: str, salt: bytes) -> str:
        """Шифрование данных паролем"""
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode('utf-8'))
        result = base64.b64encode(cipher.nonce + tag + ciphertext).decode()
        return result
    
    @staticmethod
    def decrypt_with_password(encrypted_data: str, password: str, salt: bytes) -> str:
        """Расшифровка данных паролем"""
        data = base64.b64decode(encrypted_data)
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode('utf-8')
    
    @staticmethod
    def encrypt_message(message: str, recipient_public_key: str) -> str:
        """Шифрование сообщения для конкретного получателя"""
        public_key = RSA.import_key(recipient_public_key)
        cipher_rsa = PKCS1_OAEP.new(public_key)
        
        # Генерируем случайный AES ключ
        session_key = get_random_bytes(32)
        
        # Шифруем сообщение AES-GCM
        cipher_aes = AES.new(session_key, AES.MODE_GCM)
        ciphertext, tag = cipher_aes.encrypt_and_digest(message.encode('utf-8'))
        
        # Шифруем сессионный ключ RSA
        encrypted_key = cipher_rsa.encrypt(session_key)
        
        # Формируем пакет
        package = {
            'ek': base64.b64encode(encrypted_key).decode(),
            'n': base64.b64encode(cipher_aes.nonce).decode(),
            't': base64.b64encode(tag).decode(),
            'd': base64.b64encode(ciphertext).decode()
        }
        
        return base64.b64encode(json.dumps(package).encode()).decode()
    
    @staticmethod
    def decrypt_message(encrypted_package: str, private_key: str) -> str:
        """Расшифровка сообщения своим приватным ключом"""
        try:
            # Декодируем пакет
            package = json.loads(base64.b64decode(encrypted_package).decode())
            
            private_key_obj = RSA.import_key(private_key)
            cipher_rsa = PKCS1_OAEP.new(private_key_obj)
            
            # Расшифровываем сессионный ключ
            session_key = cipher_rsa.decrypt(base64.b64decode(package['ek']))
            
            # Расшифровываем сообщение
            cipher_aes = AES.new(
                session_key,
                AES.MODE_GCM,
                nonce=base64.b64decode(package['n'])
            )
            message = cipher_aes.decrypt_and_verify(
                base64.b64decode(package['d']),
                base64.b64decode(package['t'])
            )
            
            return message.decode('utf-8')
        except Exception as e:
            print(f"Ошибка расшифровки: {e}")
            return "[Ошибка расшифровки]"
    
    @staticmethod
    def get_key_fingerprint(public_key: str) -> str:
        """Получение отпечатка ключа"""
        key = RSA.import_key(public_key)
        fingerprint = hashlib.sha256(key.export_key()).hexdigest()[:16]
        return '-'.join([fingerprint[i:i+4] for i in range(0, 16, 4)])