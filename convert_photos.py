import sqlite3
import os
from PIL import Image
from pillow_heif import register_heif_opener
register_heif_opener()

conn = sqlite3.connect("family_scrapbook.db")
cursor = conn.cursor()

cursor.execute("SELECT id, filename FROM adventure_photos")
photos = cursor.fetchall()

for photo_id, filename in photos:
    if filename.lower().endswith((".heic", ".heif")):
        old_path = f"static/uploads/{filename}"
        new_filename = filename.rsplit(".", 1)[0] + ".jpg"
        new_path = f"static/uploads/{new_filename}"
        
        try:
            img = Image.open(old_path)
            img = img.convert("RGB")
            img.save(new_path, "JPEG", quality=90)
            print(f"Converted: {filename} -> {new_filename}")
            cursor.execute("UPDATE adventure_photos SET filename = ? WHERE id = ?", (new_filename, photo_id))
            conn.commit()
        except Exception as e:
            print(f"Error converting {filename}: {e}")

conn.close()
print("All conversions complete!")