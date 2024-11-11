import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def load_spam_keywords():
    # Get the encryption key from the .env file
    key = os.getenv("ENCRYPTION_KEY").encode()  # Convert to bytes
    f = Fernet(key)

    # Load the encrypted spam_keywords file
    with open("spam_keywords.enc", "rb") as encrypted_file:
        encrypted_data = encrypted_file.read()

    # Decrypt the content
    decrypted_data = f.decrypt(encrypted_data)

    # Execute the decrypted Python code to load the spam_keywords list
    namespace = {}
    exec(decrypted_data, namespace)

    # Get the spam_keywords list from the decrypted code
    spam_keywords = namespace["spam_keywords"]

    # Create a new Python file named spam_words.py and write the spam_keywords list to it
    # with open("spam_keywords.py", "w") as spam_file:
    #     spam_file.write(f"spam_keywords = {spam_keywords}\n")

    # Return the spam_keywords list from the decrypted code
    return spam_keywords


if __name__ == "__main__":
    load_spam_keywords()
