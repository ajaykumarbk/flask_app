from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database Configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "village_blog",
}

# Helper Functions
def get_db_connection():
    """Establish and return a database connection."""
    return mysql.connector.connect(**db_config)

def allowed_file(filename):
    """Check if the file is allowed based on its extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    """Render the homepage with a list of posts and their like counts."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT posts.id, posts.title, posts.content, posts.image, users.username, posts.created_at,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """
    cursor.execute(query)
    posts = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template("index.html", posts=posts)

@app.route("/like/<int:post_id>", methods=["POST"])
def like_post(post_id):
    """Handle liking or unliking a post by the logged-in user."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Check if the user has already liked the post
    cursor.execute("SELECT id FROM likes WHERE user_id = %s AND post_id = %s", (session["user_id"], post_id))
    like = cursor.fetchone()

    if like:
        # If already liked, unlike the post
        cursor.execute("DELETE FROM likes WHERE id = %s", (like[0],))
        flash("You unliked the post.", "info")
    else:
        # Otherwise, like the post
        cursor.execute("INSERT INTO likes (user_id, post_id) VALUES (%s, %s)", (session["user_id"], post_id))
        flash("You liked the post!", "success")

    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("view_post", post_id=post_id))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            connection.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.Error:
            flash("Username already exists.", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("index"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    """Handle user logout."""
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("index"))

@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    """Allow logged-in users to create a post."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        image = request.files.get("image")

        image_path = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO posts (title, content, image, user_id) VALUES (%s, %s, %s, %s)",
            (title, content, image_path, session["user_id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Post created successfully!", "success")
        return redirect(url_for("index"))

    return render_template("create_post.html")

@app.route("/view_post/<int:post_id>")
def view_post(post_id):
    """Display a single post along with its comments and like status."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the post details
    cursor.execute("""
        SELECT posts.id, posts.title, posts.content, posts.image, users.username, posts.created_at,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = %s
    """, (post_id,))
    post = cursor.fetchone()

    # Fetch comments for the post
    cursor.execute("""
        SELECT comments.content, users.username, comments.created_at
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = %s
        ORDER BY comments.created_at
    """, (post_id,))
    comments = cursor.fetchall()

    # Check if the user liked the post
    user_liked = False
    if "user_id" in session:
        cursor.execute("SELECT id FROM likes WHERE user_id = %s AND post_id = %s", (session["user_id"], post_id))
        user_liked = cursor.fetchone() is not None

    cursor.close()
    connection.close()

    return render_template("view_post.html", post=post, comments=comments, user_liked=user_liked)

@app.route("/add_comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    """Allow logged-in users to add comments to a post."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = request.form["content"]

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (%s, %s, %s)", (content, session["user_id"], post_id))
    connection.commit()
    cursor.close()
    connection.close()

    flash("Comment added successfully!", "success")
    return redirect(url_for("view_post", post_id=post_id))

@app.route("/profile")
def profile():
    """Render the user's profile along with their posts."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch user details
    cursor.execute("SELECT id, username, bio, profile_picture FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()

    # Fetch the user's posts
    cursor.execute("""
        SELECT posts.id, posts.title, posts.created_at,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        WHERE posts.user_id = %s
        ORDER BY posts.created_at DESC
    """, (session["user_id"],))
    user_posts = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("profile.html", user=user, posts=user_posts)

@app.route("/liked_posts")
def liked_posts():
    """Show posts liked by the logged-in user."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT posts.id, posts.title, posts.content, posts.image, users.username, posts.created_at
        FROM likes
        JOIN posts ON likes.post_id = posts.id
        JOIN users ON posts.user_id = users.id
        WHERE likes.user_id = %s
        ORDER BY likes.created_at DESC
    """
    cursor.execute(query, (session["user_id"],))
    liked_posts = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("liked_posts.html", posts=liked_posts)

if __name__ == "__main__":
    app.run(debug=True)

