import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def encrypt_spam_keywords():
    # Get the encryption key from the .env file
    key = os.getenv("ENCRYPTION_KEY").encode()  # Convert to bytes

    # Load spam_keywords.py
    with open("spam_keywords.py", "rb") as file:
        data = file.read()

    # Encrypt the content
    f = Fernet(key)
    encrypted_data = f.encrypt(data)

    # Save the encrypted file
    with open("spam_keywords.enc", "wb") as encrypted_file:
        encrypted_file.write(encrypted_data)

    print("File berhasil dienkripsi dan disimpan sebagai spam_keywords.enc")


# Example usage
if __name__ == "__main__":
    encrypt_spam_keywords()
