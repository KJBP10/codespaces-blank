#!/usr/bin/env python3

import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

# File to store encrypted passwords
PASSWORD_FILE = "passwords.enc"

# Generate a key from the master password
def get_key(master_password):
    salt = b'salt_'  # In a real app, generate and store a unique salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return key

# Encrypt data
def encrypt_data(data, key):
    f = Fernet(key)
    encrypted = f.encrypt(json.dumps(data).encode())
    return encrypted

# Decrypt data
def decrypt_data(encrypted_data, key):
    f = Fernet(key)
    decrypted = json.loads(f.decrypt(encrypted_data).decode())
    return decrypted

# Load passwords from file
def load_passwords(master_password):
    key = get_key(master_password)
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, 'rb') as f:
            encrypted_data = f.read()
        try:
            return decrypt_data(encrypted_data, key)
        except:
            print("Incorrect master password or corrupted file!")
            return None
    return {}

# Save passwords to file
def save_passwords(passwords, master_password):
    key = get_key(master_password)
    encrypted_data = encrypt_data(passwords, key)
    with open(PASSWORD_FILE, 'wb') as f:
        f.write(encrypted_data)

# Add a new password
def add_password(master_password):
    passwords = load_passwords(master_password)
    if passwords is None:
        return

    site = input("Enter site/service name: ")
    username = input("Enter username: ")
    password = input("Enter password: ")

    passwords[site] = {"username": username, "password": password}
    save_passwords(passwords, master_password)
    print(f"Password for {site} added successfully!")

# Retrieve a password
def get_password(master_password):
    passwords = load_passwords(master_password)
    if passwords is None:
        return

    site = input("Enter site/service name: ")
    if site in passwords:
        print(f"Username: {passwords[site]['username']}")
        print(f"Password: {passwords[site]['password']}")
    else:
        print("No password found for that site!")

# Main menu
def main():
    master_password = input("Enter your master password: ")
    
    while True:
        print("\nPassword Manager Menu:")
        print("1. Add a password")
        print("2. Get a password")
        print("3. Exit")
        choice = input("Choose an option (1-3): ")

        if choice == "1":
            add_password(master_password)
        elif choice == "2":
            get_password(master_password)
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    main()