import sqlite3

DB_NAME = "family_scrapbook.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO events (name, year, location, description)
    VALUES (?, ?, ?, ?)
""", (
    "DeeDee and Papa Camp 2025",
    "2025",
    "Our House",
    "The first DeeDee and Papa Camp saved in the family scrapbook."
))

conn.commit()
conn.close()

print("First event added successfully.")
