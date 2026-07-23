import sqlite3

DB_NAME = "family_scrapbook.db"

def create_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            year TEXT,
            location TEXT,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            title TEXT NOT NULL,
            adventure_day TEXT,
            date TEXT,
            people TEXT,
            story TEXT,
            favorite_memory TEXT,
            funniest_moment TEXT,
            something_learned TEXT,
            thankful_for TEXT,
            rating TEXT,
            adventure_photo TEXT,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_database()
    print("Database created successfully.")