import sqlite3

conn = sqlite3.connect('family_scrapbook.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS adventure_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        caption TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        display_order INTEGER DEFAULT 0,
        FOREIGN KEY(adventure_id) REFERENCES posts(id) ON DELETE CASCADE
    )
''')

conn.commit()
conn.close()
print('adventure_photos table created successfully!')
