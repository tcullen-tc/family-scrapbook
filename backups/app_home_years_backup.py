import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

DB_NAME = "family_scrapbook.db"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def home():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events ORDER BY year DESC").fetchall()
    conn.close()
    return render_template("home.html", events=events)

@app.route("/create-event", methods=("GET", "POST"))
def create_event():
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO events (name, year, location, description)
            VALUES (?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["year"],
            request.form["location"],
            request.form["description"]
        ))

        conn.commit()
        new_event_id = cursor.lastrowid
        conn.close()

        return redirect(url_for("event_detail", event_id=new_event_id))

    return render_template("create_event.html")

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    posts = conn.execute(
        "SELECT * FROM posts WHERE event_id = ? ORDER BY date",
        (event_id,)
    ).fetchall()

    conn.close()
    return render_template("event.html", event=event, posts=posts)
@app.route("/adventure/<int:adventure_id>")
def adventure_detail(adventure_id):
    conn = get_db_connection()
    adventure = conn.execute("SELECT * FROM posts WHERE id = ?", (adventure_id,)).fetchone()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (adventure["event_id"],)).fetchone()
    conn.close()
    return render_template("adventure.html", adventure=adventure, event=event)
@app.route("/upload-photo/<int:adventure_id>", methods=("POST",))
def upload_photo(adventure_id):
    if "photo" not in request.files:
        return redirect(url_for("adventure_detail", adventure_id=adventure_id))

    photo = request.files["photo"]

    if photo.filename == "":
        return redirect(url_for("adventure_detail", adventure_id=adventure_id))

    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)
        filename = f"adventure_{adventure_id}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(filepath)

        conn = get_db_connection()
        conn.execute(
            "UPDATE posts SET adventure_photo = ? WHERE id = ?",
            (filename, adventure_id)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("adventure_detail", adventure_id=adventure_id))
@app.route("/add", methods=("GET", "POST"))
def add():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events ORDER BY year DESC").fetchall()

    if request.method == "POST":
        event_id = request.form["event_id"]

        conn.execute("""
            INSERT INTO posts (
                event_id, title, adventure_day, date, people, story,
                favorite_memory, funniest_moment, something_learned,
                thankful_for, rating
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            request.form["title"],
           request.form["location"],
            request.form["date"],
            request.form["people"],
            request.form["story"],
            request.form["favorite_memory"],
            request.form["funniest_moment"],
            request.form["something_learned"],
            request.form["thankful_for"],
            ""
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("event_detail", event_id=event_id))

    conn.close()
    return render_template("add.html", events=events)

if __name__ == "__main__":
    app.run(debug=True)
