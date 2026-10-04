
import os

import mysql.connector
from dotenv import load_dotenv

# Load variables from .env when running locally.
# Railway uses the variables configured in its service settings.
load_dotenv()


# --------------------------------------------------
# Database Configuration
# --------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "cinema_scrape"),
    "connection_timeout": 20,
}


# --------------------------------------------------
# Database Connection
# --------------------------------------------------

def get_connection():
    """Connect to the MySQL database using the configured settings."""
    return mysql.connector.connect(**DB_CONFIG)


# --------------------------------------------------
# Daily Games Table
# --------------------------------------------------

def create_daily_games_table():
    """Create the daily_games table if it does not already exist."""
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
