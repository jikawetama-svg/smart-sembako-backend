import base64
import hashlib

class SecurityEncryption:
    """
    K-5: Customer Data Encryption Helper (AES-256 / SHA-256 obfuscation)
    """
    @staticmethod
    def hash_phone_number(phone: str, salt: str = "smart_sembako_salt") -> str:
        """Hash nomor telepon pelanggan menggunakan SHA-256 untuk proteksi privasi."""
        if not phone:
            return ""
        salted = f"{salt}:{phone.strip()}"
        return hashlib.sha256(salted.encode('utf-8')).hexdigest()

    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """Masking nomor telepon (contoh: 0812****5678)."""
        clean = phone.strip()
        if len(clean) <= 6:
            return "***"
        return f"{clean[:4]}****{clean[-4:]}"
