
import mysql.connector
from mysql.connector import Error


def get_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1927",
            database="campus_resource_db"
        )
        return connection

    except Error as error:
        print("Database connection failed:", error)
        return None


if __name__ == "__main__":
    connection = get_connection()

    if connection:
        print("MySQL connected successfully!")
        connection.close()
