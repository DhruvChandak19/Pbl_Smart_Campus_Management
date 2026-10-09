
import getpass
import hashlib
from database import get_connection


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


connection = get_connection()

if connection:
    cursor = connection.cursor()

    username = input("Enter admin username: ").strip()
    full_name = input("Enter admin full name: ").strip()
    password = getpass.getpass("Create admin password: ")

    if not username or not full_name or not password:
        print("All fields are required.")
    else:
        try:
            cursor.execute(
                "INSERT INTO users "
                "(username, password_hash, full_name, role) "
                "VALUES (%s, %s, %s, %s)",
                (
                    username,
                    hash_password(password),
                    full_name,
                    "Admin"
                )
            )
            connection.commit()
            print("Admin account created successfully!")

        except Exception as error:
            connection.rollback()
            print("Could not create admin:", error)

    cursor.close()
    connection.close()
