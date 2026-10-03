
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "cinema_scrape"),
}


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def create_daily_games_table():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_games (
                id INT AUTO_INCREMENT PRIMARY KEY,
                puzzle_date DATE NOT NULL UNIQUE,
                user_id INT NOT NULL,
                hidden_film_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (hidden_film_id) REFERENCES films(id)
            )
            """
        )

        connection.commit()
        cursor.close()

    finally:
        connection.close()