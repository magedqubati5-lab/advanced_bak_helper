import os
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

class CryptoEngine:
    @staticmethod
    def generate_rsa_keypair(priv_path, pub_path):
        """
        Generates RSA 2048-bit key pair if files do not exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(priv_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(pub_path)), exist_ok=True)

        if not os.path.exists(priv_path) or not os.path.exists(pub_path):
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

            # Write private key
            with open(priv_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Write public key
            public_key = private_key.public_key()
            with open(pub_path, "wb") as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))

    @staticmethod
    def _derive_fernet(password: str, salt: bytes) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    @classmethod
    def encrypt_file(cls, input_file_path, output_enc_path, password: str):
        """
        Encrypts a file using AES-256 Fernet with salt header.
        """
        if not password:
            raise ValueError("Encryption password is required to encrypt the backup file.")

        salt = os.urandom(16)
        fernet = cls._derive_fernet(password, salt)

        with open(input_file_path, 'rb') as f_in:
            data = f_in.read()

        encrypted_data = fernet.encrypt(data)

        with open(output_enc_path, 'wb') as f_out:
            f_out.write(salt)  # First 16 bytes is salt
            f_out.write(encrypted_data)

    @classmethod
    def decrypt_file(cls, input_enc_path, output_file_path, password: str):
        """
        Decrypts an encrypted file using the password.
        """
        if not password:
            raise ValueError("Password is required to decrypt the backup file.")

        with open(input_enc_path, 'rb') as f_in:
            salt = f_in.read(16)
            encrypted_data = f_in.read()

        fernet = cls._derive_fernet(password, salt)
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
        except Exception:
            raise ValueError("Decryption failed: Incorrect password or corrupted payload.")

        with open(output_file_path, 'wb') as f_out:
            f_out.write(decrypted_data)

    @staticmethod
    def sign_file(file_path, private_key_path, output_sig_path):
        """
        Signs a file using RSA private key and SHA256 digest.
        """
        if not os.path.exists(private_key_path):
            raise FileNotFoundError(f"RSA Private key not found for signing: {private_key_path}")

        with open(private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
            )

        with open(file_path, "rb") as f:
            file_data = f.read()

        signature = private_key.sign(
            file_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        with open(output_sig_path, "wb") as f_sig:
            f_sig.write(signature)

    @staticmethod
    def verify_signature(file_path, signature_path, public_key_path) -> bool:
        """
        Verifies signature of a file using RSA public key.
        Returns True if valid signature, False otherwise.
        """
        if not os.path.exists(public_key_path) or not os.path.exists(signature_path):
            return False

        with open(public_key_path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read()
            )

        with open(signature_path, "rb") as f_sig:
            signature = f_sig.read()

        with open(file_path, "rb") as f:
            file_data = f.read()

        try:
            public_key.verify(
                signature,
                file_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
