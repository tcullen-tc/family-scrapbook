import sqlite3

DB_NAME = "family_scrapbook.db"

def create_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ==================== FAMILIES TABLE ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ==================== USERS TABLE ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY(family_id) REFERENCES families(id)
        )
    """)

    # ==================== EVENTS TABLE (ADVENTURES) ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            year TEXT,
            location TEXT,
            description TEXT,
            FOREIGN KEY(family_id) REFERENCES families(id)
        )
    """)

    # ==================== POSTS TABLE (MEMORIES) ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
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
            hero_caption TEXT,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY(family_id) REFERENCES families(id),
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    """)

    # ==================== ADVENTURE PHOTOS TABLE ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adventure_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            adventure_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            caption TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY(family_id) REFERENCES families(id),
            FOREIGN KEY(adventure_id) REFERENCES posts(id) ON DELETE CASCADE
        )
    """)

    # ==================== FAMILY MEMBERS TABLE ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            nickname TEXT,
            birth_date TEXT,
            photo TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(family_id) REFERENCES families(id)
        )
    """)

    # ==================== MEMORY PEOPLE TABLE ====================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id INTEGER NOT NULL,
            family_member_id INTEGER NOT NULL,
            FOREIGN KEY(memory_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY(family_member_id) REFERENCES family_members(id) ON DELETE CASCADE,
            UNIQUE(memory_id, family_member_id)
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_database()
    print("Database created successfully with multi-family support!")