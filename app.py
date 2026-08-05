# Logging enabled for Render

import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
from PIL import Image
from pillow_heif import register_heif_opener
from flask_mail import Mail, Message
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import logging
app = Flask(__name__)
app.secret_key = 'family-memories-secret-key'
# Ensure the upload directory exists
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'cullenfamily.memories@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'cullenfamily.memories@gmail.com')

mail = Mail(app)

# Register HEIC/HEIF support
register_heif_opener()

DB_NAME = "family_scrapbook.db"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic", "heif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== USER AUTHENTICATION ====================

class User(UserMixin):
    def __init__(self, id, family_id, username, email, full_name, is_admin):
        self.id = id
        self.family_id = family_id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.is_admin = is_admin

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(
            user["id"],
            user["family_id"],
            user["username"],
            user["email"],
            user["full_name"],
            user["is_admin"]
        )
    return None

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# ==================== REGISTER ====================

@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        family_name = request.form.get("family_name", "My Family")
        
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()
        
        if existing:
            conn.close()
            return "Username or email already exists. Please try again.", 400
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO families (name) VALUES (?)",
            (family_name,)
        )
        family_id = cursor.lastrowid
        hashed_password = generate_password_hash(password)
        
        conn.execute(
            "INSERT INTO users (family_id, username, email, password, full_name, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
            (family_id, username, email, hashed_password, full_name, 1)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("login"))
    
    return render_template("register.html")

# ==================== LOGIN ====================

@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password"], password):
            user_obj = User(
                user["id"],
                user["family_id"],
                user["username"],
                user["email"],
                user["full_name"],
                user["is_admin"]
            )
            login_user(user_obj)
            conn = get_db_connection()
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            conn.commit()
            conn.close()
            return redirect(url_for("home"))
        else:
            return "Invalid username or password. Please try again.", 401
    
    return render_template("login.html")

# ==================== LOGOUT ====================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ==================== HOME ====================

@app.route("/")
def home():
    # If user is not logged in, redirect to login page
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    
    # Get all events and attach one adventure_photo for each event (if any exist)
    events = conn.execute("""
    SELECT events.*, 
        (SELECT adventure_photo FROM posts WHERE event_id = events.id AND adventure_photo IS NOT NULL LIMIT 1) as adventure_photo
        FROM events 
        ORDER BY year DESC
    """).fetchall()
    
    # Get one random post with a photo to feature at the top of the page
    featured_adventure = conn.execute("""
        SELECT posts.*, events.name AS event_name
        FROM posts
        JOIN events ON posts.event_id = events.id
        WHERE posts.adventure_photo IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 1
    """).fetchone()
    
    conn.close()
    
    events_by_year = {}
    for event in events:
        year = event["year"]
        if year not in events_by_year:
            events_by_year[year] = []
        events_by_year[year].append(event)
        
    return render_template(
        "home.html",
        events_by_year=events_by_year,
        featured_adventure=featured_adventure
    )

# ==================== CREATE ADVENTURE ====================

@app.route("/create-adventure", methods=("GET", "POST"))
def create_adventure():
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
    INSERT INTO events (family_id, name, month, year, location, description)
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    current_user.family_id,
    request.form["name"],
    request.form["month"],
    request.form["year"],
    request.form["location"],
    request.form["description"]
))
        conn.commit()
        new_event_id = cursor.lastrowid
        conn.close()
        return redirect(url_for("adventure_detail", adventure_id=new_event_id))
    return render_template("create_adventure.html")

# ==================== ADVENTURE DETAIL ====================

@app.route("/adventure/<int:adventure_id>")
def adventure_detail(adventure_id):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ? AND family_id = ?", (adventure_id, current_user.family_id)).fetchone()
    if event is None:
        conn.close()
        return "Adventure not found", 404
    posts = conn.execute(
        "SELECT * FROM posts WHERE event_id = ? AND family_id = ? ORDER BY date",
        (adventure_id, current_user.family_id)
    ).fetchall()
    conn.close()
    return render_template("event.html", event=event, posts=posts)

# ==================== MEMORY DETAIL ====================

@app.route("/memory/<int:memory_id>")
def memory_detail(memory_id):
    conn = get_db_connection()
    adventure = conn.execute("SELECT * FROM posts WHERE id = ? AND family_id = ?", (memory_id, current_user.family_id)).fetchone()
    if adventure is None:
        conn.close()
        return "Memory not found", 404
    event = conn.execute("SELECT * FROM events WHERE id = ?", (adventure["event_id"],)).fetchone()
    additional_photos = conn.execute(
        "SELECT * FROM adventure_photos WHERE adventure_id = ? ORDER BY display_order, uploaded_at",
        (memory_id,)
    ).fetchall()
    tagged_people = conn.execute("""
        SELECT family_members.* 
        FROM family_members
        JOIN memory_people ON family_members.id = memory_people.family_member_id
        WHERE memory_people.memory_id = ?
        ORDER BY family_members.name
    """, (memory_id,)).fetchall()
    
    # Get comments
    comments = conn.execute("""
        SELECT comments.*, users.username 
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.memory_id = ?
        ORDER BY comments.created_at DESC
    """, (memory_id,)).fetchall()
    
    conn.close()
    return render_template("adventure.html", 
                          adventure=adventure, 
                          event=event, 
                          additional_photos=additional_photos,
                          tagged_people=tagged_people,
                          comments=comments)

# ==================== CREATE MEMORY ====================

@app.route("/add", methods=["GET", "POST"])
@app.route("/add/<int:adventure_id>", methods=["GET", "POST"])
def add(adventure_id=None):
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events ORDER BY year DESC").fetchall()
    family_members = conn.execute("SELECT * FROM family_members WHERE family_id = ? ORDER BY name", (current_user.family_id,)).fetchall()
    
    if request.method == "POST":
        # Get the hidden adventure ID from the form
        event_id = request.form["event_id"]
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posts (
                family_id, event_id, title, adventure_day, date, story,
                favorite_memory, funniest_moment, something_learned,
                thankful_for, rating
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user.family_id,
            event_id,
            request.form["title"],
            request.form["location"],
            request.form["date"],
            request.form["story"],
            request.form["favorite_memory"],
            request.form["funniest_moment"],
            request.form["something_learned"],
            request.form["thankful_for"],
            ""
        ))
        new_memory_id = cursor.lastrowid
        conn.commit()

        # Save family member tags
        selected_members = request.form.getlist("family_members")
        for member_id in selected_members:
            conn.execute(
                "INSERT INTO memory_people (memory_id, family_member_id) VALUES (?, ?)",
                (new_memory_id, member_id)
            )

        # Handle hero photo
        if "hero_photo" in request.files:
            photo = request.files["hero_photo"]
            if photo and photo.filename != "" and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                filename = f"adventure_{new_memory_id}_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                photo.save(filepath)
                conn.execute(
                    "UPDATE posts SET adventure_photo = ? WHERE id = ?",
                    (filename, new_memory_id)
                )
                conn.commit()
                print(f"Hero photo saved: {filename}")

        # Handle additional photos
        if "additional_photos" in request.files:
            files = request.files.getlist("additional_photos")
            caption = request.form.get("additional_photos_caption", "")
            for idx, photo in enumerate(files):
                if photo and photo.filename != "" and allowed_file(photo.filename):
                    filename = secure_filename(photo.filename)
                    filename = f"adventure_{new_memory_id}_{idx}_{filename}"
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    photo.save(filepath)
                    conn.execute(
                        "INSERT INTO adventure_photos (family_id, adventure_id, filename, caption, display_order) VALUES (?, ?, ?, ?, ?)",
                        (current_user.family_id, new_memory_id, filename, caption, idx)
                    )
                    conn.commit()
                    print(f"Additional photo saved: {filename}")

        conn.close()
        return redirect(url_for("memory_detail", memory_id=new_memory_id))

    conn.close()
    # Pass the adventure_id to the template so it can be used in the hidden input
    return render_template("add.html", events=events, family_members=family_members, adventure_id=adventure_id)

# ==================== EDIT ADVENTURE (EVENT) ====================

@app.route("/edit-adventure-page/<int:event_id>", methods=("GET", "POST"))
def edit_adventure_page(event_id):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    
    if event is None:
        conn.close()
        return "Adventure not found", 404
    
    if request.method == "POST":
        name = request.form["name"]
        month = request.form.get("month", "")
        year = request.form["year"]
        location = request.form["location"]
        description = request.form["description"]
        
        conn.execute(
            "UPDATE events SET name = ?, month = ?, year = ?, location = ?, description = ? WHERE id = ?",
            (name, month, year, location, description, event_id)
        )
        conn.commit()
        conn.close()
        
        return redirect(url_for("adventure_detail", adventure_id=event_id))
    
    conn.close()
    return render_template("edit_adventure.html", event=event)
# ==================== DELETE ADVENTURE (EVENT) ====================

@app.route("/delete-adventure-page/<int:event_id>")
def delete_adventure_page(event_id):
    conn = get_db_connection()
    posts = conn.execute("SELECT id FROM posts WHERE event_id = ?", (event_id,)).fetchall()
    for post in posts:
        photos = conn.execute("SELECT filename FROM adventure_photos WHERE adventure_id = ?", (post["id"],)).fetchall()
        for photo in photos:
            filepath = os.path.join(UPLOAD_FOLDER, photo["filename"])
            if os.path.exists(filepath):
                os.remove(filepath)
        post_data = conn.execute("SELECT adventure_photo FROM posts WHERE id = ?", (post["id"],)).fetchone()
        if post_data and post_data["adventure_photo"]:
            filepath = os.path.join(UPLOAD_FOLDER, post_data["adventure_photo"])
            if os.path.exists(filepath):
                os.remove(filepath)
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

# ==================== EDIT MEMORY ====================

@app.route("/edit-adventure/<int:adventure_id>", methods=("GET",))
def edit_adventure(adventure_id):
    conn = get_db_connection()
    adventure = conn.execute("SELECT * FROM posts WHERE id = ? AND family_id = ?", (adventure_id, current_user.family_id)).fetchone()
    if adventure is None:
        conn.close()
        return "Memory not found", 404
    additional_photos = conn.execute(
        "SELECT * FROM adventure_photos WHERE adventure_id = ? ORDER BY display_order, uploaded_at",
        (adventure_id,)
    ).fetchall()
    family_members = conn.execute(
        "SELECT * FROM family_members WHERE family_id = ? ORDER BY name",
        (current_user.family_id,)
    ).fetchall()
    tagged = conn.execute(
        "SELECT family_member_id FROM memory_people WHERE memory_id = ?",
        (adventure_id,)
    ).fetchall()
    tagged_member_ids = [t["family_member_id"] for t in tagged]
    conn.close()
    return render_template("edit_memory.html", 
                          adventure=adventure, 
                          additional_photos=additional_photos,
                          family_members=family_members,
                          tagged_member_ids=tagged_member_ids)

# ==================== UPDATE MEMORY ====================

@app.route("/upload-photo/<int:adventure_id>", methods=("POST",))
def upload_photo(adventure_id):
    print("=" * 50)
    print("UPLOAD PHOTO CALLED")
    print("Adventure ID:", adventure_id)
    print("=" * 50)
    
    if "photo" not in request.files:
        print("No photo in request")
        return redirect(url_for("adventure_detail", adventure_id=adventure_id))

    photo = request.files["photo"]
    print("Photo filename:", photo.filename)

    if photo.filename == "":
        print("Empty filename")
        return redirect(url_for("adventure_detail", adventure_id=adventure_id))

    if photo and allowed_file(photo.filename):
        is_heic = photo.filename.lower().endswith(('.heic', '.heif'))
        original_name = os.path.splitext(photo.filename)[0]
        safe_name = secure_filename(original_name)
        
        if is_heic:
            try:
                img = Image.open(photo)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize image to max 1200px
                max_size = 1200
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    print(f"Resized image to {new_width}x{new_height}")
                
                filename = f"adventure_{adventure_id}_{safe_name}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                img.save(filepath, 'JPEG', quality=85)
                print(f"HEIC converted and saved: {filename}")
            except Exception as e:
                print(f"Error converting HEIC: {e}")
                return redirect(url_for("adventure_detail", adventure_id=adventure_id))
        else:
            filename = secure_filename(photo.filename)
            filename = f"adventure_{adventure_id}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(filepath)
            print(f"Photo saved: {filename}")

        conn = get_db_connection()
        conn.execute(
            "UPDATE posts SET adventure_photo = ? WHERE id = ?",
            (filename, adventure_id)
        )
        
        # Save hero caption if provided
        hero_caption = request.form.get("hero_caption", "")
        if hero_caption:
            conn.execute(
                "UPDATE posts SET hero_caption = ? WHERE id = ?",
                (hero_caption, adventure_id)
            )
            print(f"Hero caption saved: {hero_caption}")
        
        conn.commit()
        conn.close()
        print(f"Database updated: {filename}")

    return redirect(url_for("memory_detail", memory_id=adventure_id))



# ==================== UPLOAD ADDITIONAL PHOTOS ====================

@app.route("/upload-adventure-photos/<int:adventure_id> ", methods=("POST",))
def upload_adventure_photos(adventure_id):
    print("=== UPLOAD ADVENTURE PHOTOS STARTED ===")
    print("=" * 50)
    print("UPLOAD ADDITIONAL PHOTOS CALLED")
    print("Adventure ID:", adventure_id)
    print("=" * 50)
    
    if "photos" not in request.files:
        return redirect(url_for("edit_adventure", adventure_id=adventure_id))
    
    files = request.files.getlist("photos")
    caption = request.form.get("caption", "")
    
    if not files or files[0].filename == "":
        return redirect(url_for("edit_adventure", adventure_id=adventure_id))
    
    conn = get_db_connection()
    current_count = conn.execute(
        "SELECT COUNT(*) FROM adventure_photos WHERE adventure_id = ?",
        (adventure_id,)
    ).fetchone()[0]
    conn.close()
    
    uploaded_count = 0
    for photo in files:
        print(f"Processing file: {photo.filename}")
        if photo and allowed_file(photo.filename):
            # Check if it's a HEIC file
            is_heic = photo.filename.lower().endswith(('.heic', '.heif'))
            original_name = os.path.splitext(photo.filename)[0]
            safe_name = secure_filename(original_name)
            
            if is_heic:
                try:
                    # Convert HEIC to JPG
                    img = Image.open(photo)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Resize image to max 1200px
                    max_size = 1200
                    if img.width > max_size or img.height > max_size:
                        ratio = min(max_size / img.width, max_size / img.height)
                        new_width = int(img.width * ratio)
                        new_height = int(img.height * ratio)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        print(f"Resized additional image to {new_width}x{new_height}")
                    
                    filename = f"adventure_{adventure_id}_{uploaded_count}_{safe_name}.jpg"
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    img.save(filepath, 'JPEG', quality=85)
                    print(f"HEIC converted and saved: {filename}")
                except Exception as e:
                    print(f"Error converting HEIC: {e}")
                    continue
            else:
                # For non-HEIC files, save normally
                filename = secure_filename(photo.filename)
                filename = f"adventure_{adventure_id}_{uploaded_count}_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                photo.save(filepath)
                print(f"Photo saved: {filename}")
            
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO adventure_photos (family_id, adventure_id, filename, caption, display_order) VALUES (?, ?, ?, ?, ?)",
                (current_user.family_id, adventure_id, filename, caption, current_count + uploaded_count)
            )
            conn.commit()
            conn.close()
            uploaded_count += 1
    
    return redirect(url_for("edit_adventure", adventure_id=adventure_id))

# ==================== DELETE PHOTO ====================

@app.route("/delete-photo/<int:photo_id>")
def delete_photo(photo_id):
    conn = get_db_connection()
    photo = conn.execute("SELECT adventure_id, filename FROM adventure_photos WHERE id = ?", (photo_id,)).fetchone()
    if photo:
        adventure_id = photo["adventure_id"]
        filename = photo["filename"]
        conn.execute("DELETE FROM adventure_photos WHERE id = ?", (photo_id,))
        conn.commit()
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.close()
        return redirect(url_for("edit_adventure", adventure_id=adventure_id))
    conn.close()
    return redirect(url_for("home"))

# ==================== DELETE MEMORY ====================

@app.route("/delete-adventure/<int:adventure_id>")
def delete_adventure(adventure_id):
    conn = get_db_connection()
    adventure = conn.execute("SELECT event_id FROM posts WHERE id = ? AND family_id = ?", (adventure_id, current_user.family_id)).fetchone()
    event_id = adventure["event_id"] if adventure else None
    conn.execute("DELETE FROM posts WHERE id = ?", (adventure_id,))
    conn.commit()
    conn.close()
    if event_id:
        return redirect(url_for("adventure_detail", adventure_id=event_id))
    else:
        return redirect(url_for("home"))

# ==================== FAMILY MEMBERS ====================

@app.route("/family-members")
def family_members():
    conn = get_db_connection()
    members = conn.execute("SELECT * FROM family_members ORDER BY name").fetchall()
    conn.close()
    return render_template("family_members.html", members=members)

@app.route("/add-family-member", methods=("GET", "POST"))
def add_family_member():
    if request.method == "POST":
        name = request.form["name"]
        nickname = request.form.get("nickname", "")
        birth_date = request.form.get("birth_date", "")
        bio = request.form.get("bio", "")
        email = request.form.get("email", "")
        
        photo_filename = None
        if "photo" in request.files:
            photo = request.files["photo"]
            if photo and photo.filename != "" and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                photo_filename = f"family_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, photo_filename)
                photo.save(filepath)
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO family_members (family_id, name, nickname, birth_date, photo, bio, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (current_user.family_id, name, nickname, birth_date, photo_filename, bio, email)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("add"))
    
    return render_template("add_family_member.html")

@app.route("/family-member/<int:member_id>")
def family_member_detail(member_id):
    conn = get_db_connection()
    member = conn.execute("SELECT * FROM family_members WHERE id = ?", (member_id,)).fetchone()
    if member is None:
        conn.close()
        return "Family member not found", 404
    memories = conn.execute("""
        SELECT posts.*, events.name as event_name
        FROM posts
        JOIN memory_people ON posts.id = memory_people.memory_id
        JOIN events ON posts.event_id = events.id
        WHERE memory_people.family_member_id = ?
        ORDER BY posts.date DESC
    """, (member_id,)).fetchall()
    conn.close()
    return render_template("family_member_detail.html", member=member, memories=memories)

@app.route("/edit-family-member/<int:member_id>", methods=("GET", "POST"))
def edit_family_member(member_id):
    conn = get_db_connection()
    member = conn.execute("SELECT * FROM family_members WHERE id = ? AND family_id = ?", (member_id, current_user.family_id)).fetchone()
    if member is None:
        conn.close()
        return "Family member not found", 404
    if request.method == "POST":
        name = request.form["name"]
        nickname = request.form.get("nickname", "")
        birth_date = request.form.get("birth_date", "")
        bio = request.form.get("bio", "")
        email = request.form.get("email", "")
        photo_filename = member["photo"]
        if "photo" in request.files:
            photo = request.files["photo"]
            if photo and photo.filename != "" and allowed_file(photo.filename):
                if member["photo"]:
                    old_path = os.path.join(UPLOAD_FOLDER, member["photo"])
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(photo.filename)
                photo_filename = f"family_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, photo_filename)
                photo.save(filepath)
        conn.execute(
            "UPDATE family_members SET name = ?, nickname = ?, birth_date = ?, photo = ?, bio = ?, email = ? WHERE id = ? AND family_id = ?",
            (name, nickname, birth_date, photo_filename, bio, email, member_id, current_user.family_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("family_member_detail", member_id=member_id))
    conn.close()
    return render_template("edit_family_member.html", member=member)

@app.route("/delete-family-member/<int:member_id>")
def delete_family_member(member_id):
    conn = get_db_connection()
    member = conn.execute("SELECT photo FROM family_members WHERE id = ?", (member_id,)).fetchone()
    if member and member["photo"]:
        photo_path = os.path.join(UPLOAD_FOLDER, member["photo"])
        if os.path.exists(photo_path):
            os.remove(photo_path)
    conn.execute("DELETE FROM family_members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("family_members"))

# ==================== PHOTO CAPTIONS ====================

@app.route("/update-photo-caption/<int:photo_id>", methods=("POST",))
def update_photo_caption(photo_id):
    caption = request.form.get("caption", "")
    conn = get_db_connection()
    photo = conn.execute("SELECT adventure_id FROM adventure_photos WHERE id = ?", (photo_id,)).fetchone()
    if photo:
        conn.execute(
            "UPDATE adventure_photos SET caption = ? WHERE id = ?",
            (caption, photo_id)
        )
        conn.commit()
        adventure_id = photo["adventure_id"]
        conn.close()
        return redirect(url_for("edit_adventure", adventure_id=adventure_id))
    conn.close()
    return redirect(url_for("home"))

@app.route("/update-all-captions/<int:adventure_id>", methods=("POST",))
def update_all_captions(adventure_id):
    conn = get_db_connection()
    photos = conn.execute("SELECT id FROM adventure_photos WHERE adventure_id = ?", (adventure_id,)).fetchall()
    for photo in photos:
        caption_key = f"caption_{photo['id']}"
        caption = request.form.get(caption_key, "")
        conn.execute(
            "UPDATE adventure_photos SET caption = ? WHERE id = ?",
            (caption, photo['id'])
        )
    conn.commit()
    conn.close()
    return redirect(url_for("edit_adventure", adventure_id=adventure_id))

# ==================== SHARE MEMORY ====================

@app.route("/share-memory/<int:adventure_id>", methods=("POST",))
def share_memory(adventure_id):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io
    from PIL import Image as PILImage
    
    recipient = request.form.get("recipient_email", "")
    personal_message = request.form.get("personal_message", "")
    share_format = request.form.get("share_format", "pdf")
    
    if not recipient:
        return "Please enter a recipient email", 400
    
    conn = get_db_connection()
    adventure = conn.execute("SELECT * FROM posts WHERE id = ?", (adventure_id,)).fetchone()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (adventure["event_id"],)).fetchone()
    additional_photos = conn.execute(
        "SELECT * FROM adventure_photos WHERE adventure_id = ? ORDER BY display_order",
        (adventure_id,)
    ).fetchall()
    conn.close()
    
    if adventure is None:
        return "Memory not found", 404
    
    subject = f"Family Memory: {adventure['title']}"
    html_body = build_email_html(adventure, event, personal_message)
    
    msg = Message(subject, recipients=[recipient])
    msg.html = html_body
    
    if share_format == "pdf":
        pdf_buffer = create_memory_pdf(adventure, event, additional_photos, personal_message)
        msg.attach(f"{adventure['title']}.pdf", "application/pdf", pdf_buffer.getvalue())
        if adventure['adventure_photo']:
            try:
                with app.open_resource(f"static/uploads/{adventure['adventure_photo']}") as fp:
                    msg.attach(adventure['adventure_photo'], "image/jpeg", fp.read())
            except:
                pass
    else:
        if adventure['adventure_photo']:
            try:
                compressed = compress_image(f"static/uploads/{adventure['adventure_photo']}")
                msg.attach(f"hero_{adventure['adventure_photo']}", "image/jpeg", compressed)
            except Exception as e:
                print(f"Could not attach hero photo: {e}")
        for photo in additional_photos:
            try:
                compressed = compress_image(f"static/uploads/{photo['filename']}")
                msg.attach(photo['filename'], "image/jpeg", compressed)
            except Exception as e:
                print(f"Could not attach photo: {e}")
    
    try:
        print(f"Attempting to send email to: {recipient}")
        print(f"Subject: {subject}")
        mail.send(msg)
        print("Email sent successfully!")
        return render_template("share_success.html", recipient=recipient, memory_title=adventure['title'], adventure_id=adventure_id)
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return f"Error sending email: {str(e)}", 500

def build_email_html(adventure, event, personal_message):
    html = f"""
    <html>
    <body style="font-family: Georgia, serif; background-color: #f5f0e8; padding: 30px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; border: 2px solid #b8943c;">
            <h1 style="color: #3d2b1f; text-align: center;">📖 {adventure['title']}</h1>
            <p style="color: #6b4c3a; text-align: center; font-style: italic;">{event['name']} • {adventure['date']}</p>
            <hr style="border-color: #b8943c;">
            <p><strong>Location:</strong> {adventure['adventure_day']}</p>
            <p><strong>Date:</strong> {adventure['date']}</p>
            <p><strong>People:</strong> {adventure['people']}</p>
            <h3>✨ The Story</h3>
            <p style="line-height: 1.8;">{adventure['story']}</p>
    """
    if adventure['favorite_memory']:
        html += f"<h4>❤️ Favorite Memory</h4><p>{adventure['favorite_memory']}</p>"
    if adventure['funniest_moment']:
        html += f"<h4>😂 Funniest Moment</h4><p>{adventure['funniest_moment']}</p>"
    if personal_message:
        html += f"""
            <hr style="border-color: #b8943c;">
            <h3>💬 Personal Message</h3>
            <p style="font-style: italic; color: #6b4c3a;">{personal_message}</p>
        """
    html += f"""
            <hr style="border-color: #b8943c;">
            <p style="color: #8b6b4a; font-size: 12px; text-align: center;">
                Sent from Family Memories • <a href="http://127.0.0.1:5000/adventure/{adventure['id']}">View this memory online</a>
            </p>
        </div>
    </body>
    </html>
    """
    return html

def create_memory_pdf(adventure, event, additional_photos, personal_message):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io
    from PIL import Image as PILImage, ImageOps
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#3d2b1f',
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor='#6b4c3a',
        alignment=TA_CENTER,
        fontStyle='italic',
        spaceAfter=20
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        textColor='#3d2b1f',
        alignment=TA_LEFT,
        spaceAfter=6
    )
    
    # Title
    story.append(Paragraph(f"📖 {adventure['title']}", title_style))
    story.append(Paragraph(f"{event['name']} • {adventure['date']}", subtitle_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Hero Photo
    if adventure['adventure_photo']:
        try:
            img_path = f"static/uploads/{adventure['adventure_photo']}"
            img = PILImage.open(img_path)
            
            # Fix orientation from EXIF data
            try:
                img = ImageOps.exif_transpose(img)
            except:
                pass
            
            img_width, img_height = img.size
            max_width = 5 * inch
            max_height = 7 * inch
            
            ratio = min(max_width / img_width, max_height / img_height, 1)
            if ratio < 1:
                img_width = img_width * ratio
                img_height = img_height * ratio
            
            img = img.resize((int(img_width), int(img_height)), PILImage.LANCZOS)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            rl_img = RLImage(img_buffer, width=img_width, height=img_height)
            story.append(rl_img)
            story.append(Spacer(1, 0.1*inch))
            
            if adventure['hero_caption']:
                caption_style = ParagraphStyle(
                    'Caption',
                    parent=styles['Normal'],
                    fontSize=10,
                    textColor='#6b4c3a',
                    alignment=TA_CENTER,
                    fontStyle='italic'
                )
                story.append(Paragraph(adventure['hero_caption'], caption_style))
                story.append(Spacer(1, 0.2*inch))
        except Exception as e:
            print(f"Could not add hero photo to PDF: {e}")
    
    # Details
    story.append(Paragraph(f"<b>Location:</b> {adventure['adventure_day']}", body_style))
    story.append(Paragraph(f"<b>Date:</b> {adventure['date']}", body_style))
    story.append(Paragraph(f"<b>People:</b> {adventure['people']}", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Story
    story.append(Paragraph("<b>✨ The Story</b>", body_style))
    story.append(Paragraph(adventure['story'], body_style))
    story.append(Spacer(1, 0.1*inch))
    
    if adventure['favorite_memory']:
        story.append(Paragraph("<b>❤️ Favorite Memory</b>", body_style))
        story.append(Paragraph(adventure['favorite_memory'], body_style))
    if adventure['funniest_moment']:
        story.append(Paragraph("<b>😂 Funniest Moment</b>", body_style))
        story.append(Paragraph(adventure['funniest_moment'], body_style))
    
    if personal_message:
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("<b>💬 Personal Message</b>", body_style))
        story.append(Paragraph(personal_message, body_style))
    
    # Additional Photos
    if additional_photos:
        story.append(PageBreak())
        story.append(Paragraph("📸 Additional Photos", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        for photo in additional_photos:
            try:
                img_path = f"static/uploads/{photo['filename']}"
                img = PILImage.open(img_path)
                
                # Fix orientation from EXIF data
                try:
                    img = ImageOps.exif_transpose(img)
                except:
                    pass
                
                img_width, img_height = img.size
                max_width = 4 * inch
                max_height = 5 * inch
                
                ratio = min(max_width / img_width, max_height / img_height, 1)
                if ratio < 1:
                    img_width = img_width * ratio
                    img_height = img_height * ratio
                
                img = img.resize((int(img_width), int(img_height)), PILImage.LANCZOS)
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)
                rl_img = RLImage(img_buffer, width=img_width, height=img_height)
                story.append(rl_img)
                story.append(Spacer(1, 0.05*inch))
                
                if photo['caption']:
                    caption_style = ParagraphStyle(
                        'PhotoCaption',
                        parent=styles['Normal'],
                        fontSize=10,
                        textColor='#6b4c3a',
                        alignment=TA_CENTER,
                        fontStyle='italic'
                    )
                    story.append(Paragraph(photo['caption'], caption_style))
                story.append(Spacer(1, 0.2*inch))
            except Exception as e:
                print(f"Could not add photo to PDF: {e}")
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def compress_image(filepath, max_size_mb=2):
    from PIL import Image as PILImage
    import io
    
    img = PILImage.open(filepath)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')
    
    quality = 85
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality)
    while len(buffer.getvalue()) > max_size_mb * 1024 * 1024 and quality > 20:
        quality -= 10
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
    if len(buffer.getvalue()) > max_size_mb * 1024 * 1024:
        width, height = img.size
        ratio = min(1, (max_size_mb * 1024 * 1024) / len(buffer.getvalue()))
        new_width = int(width * ratio * 0.8)
        new_height = int(height * ratio * 0.8)
        img = img.resize((new_width, new_height), PILImage.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    return buffer.getvalue()

# ==================== MAP ====================

@app.route("/map")
def map_view():
    conn = get_db_connection()
    memories = conn.execute("""
        SELECT posts.*, events.name as event_name
        FROM posts
        JOIN events ON posts.event_id = events.id
        WHERE posts.latitude IS NOT NULL 
        AND posts.longitude IS NOT NULL
        AND posts.family_id = ?
    """, (current_user.family_id,)).fetchall()
    conn.close()
    return render_template("map.html", memories=memories)

@app.route("/update-coordinates")
def update_coordinates():
    conn = get_db_connection()
    memories = conn.execute("""
        SELECT id, adventure_day FROM posts 
        WHERE latitude IS NULL OR longitude IS NULL
    """).fetchall()
    if not memories:
        conn.close()
        return "All memories already have coordinates!"
    geolocator = Nominatim(user_agent="family_memories")
    updated_count = 0
    failed = []
    for memory in memories:
        location = memory["adventure_day"]
        if location:
            try:
                geo = geolocator.geocode(location, timeout=10)
                if geo:
                    conn.execute(
                        "UPDATE posts SET latitude = ?, longitude = ? WHERE id = ?",
                        (geo.latitude, geo.longitude, memory["id"])
                    )
                    conn.commit()
                    updated_count += 1
                    print(f"✅ {location} → ({geo.latitude}, {geo.longitude})")
                else:
                    failed.append(location)
                    print(f"❌ Could not find: {location}")
            except Exception as e:
                failed.append(location)
                print(f"❌ Error geocoding {location}: {e}")
    conn.close()
    message = f"Updated {updated_count} memories."
    if failed:
        message += f" Could not find: {', '.join(failed[:5])}"
        if len(failed) > 5:
            message += f" and {len(failed)-5} more"
    return message

# ==================== COMMENTS ====================

@app.route("/add-comment/<int:memory_id>", methods=("POST",))
@login_required
def add_comment(memory_id):
    comment = request.form.get("comment", "").strip()
    
    if not comment:
        return "Comment cannot be empty", 400
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO comments (memory_id, user_id, comment) VALUES (?, ?, ?)",
        (memory_id, current_user.id, comment)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for("memory_detail", memory_id=memory_id))

if __name__ == "__main__":
    app.run(debug=True)