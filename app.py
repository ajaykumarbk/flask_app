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

# Database Configuration (Hardcoded directly into the file)
db_config = {
    "host": "db",  # Replace with your DB host (e.g., "localhost" or EC2 IP)
    "user": "root",       # Replace with your DB username
    "password": "admin",  # Replace with your DB password
    "database": "blog",  # Replace with your DB name
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

@app.route("/delete_post/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    """Allow users to delete their posts."""
    if "user_id" not in session:
        flash("You need to log in to delete posts.", "danger")
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Check if the post belongs to the logged-in user
    cursor.execute("SELECT user_id FROM posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    if not post or post[0] != session["user_id"]:
        cursor.close()
        connection.close()
        flash("You do not have permission to delete this post.", "danger")
        return redirect(url_for("index"))

    # Delete the post and associated comments and likes
    cursor.execute("DELETE FROM likes WHERE post_id = %s", (post_id,))
    cursor.execute("DELETE FROM comments WHERE post_id = %s", (post_id,))
    cursor.execute("DELETE FROM posts WHERE id = %s", (post_id,))
    connection.commit()

    cursor.close()
    connection.close()

    flash("Post deleted successfully.", "success")
    return redirect(url_for("index"))

# Search users functionality
@app.route("/search_users", methods=["GET", "POST"])
def search_users():
    """Search for other users by username."""
    if "user_id" not in session:
        flash("Please log in to search for users.", "danger")
        return redirect(url_for("login"))

    users = []
    if request.method == "POST":
        search_query = request.form["search_query"]
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username FROM users WHERE username LIKE %s AND id != %s",
            (f"%{search_query}%", session["user_id"])
        )
        users = cursor.fetchall()
        cursor.close()
        connection.close()

    return render_template("search_users.html", users=users)

# Friend request handling
@app.route("/send_friend_request/<int:receiver_id>", methods=["POST"])
def send_friend_request(receiver_id):
    """Send a friend request to another user."""
    if "user_id" not in session:
        flash("Please log in to send friend requests.", "danger")
        return redirect(url_for("login"))

    sender_id = session["user_id"]

    connection = get_db_connection()
    cursor = connection.cursor()

    # Check if a friend request already exists
    cursor.execute(
        "SELECT id FROM friend_requests WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'",
        (sender_id, receiver_id)
    )
    existing_request = cursor.fetchone()

    if existing_request:
        flash("Friend request already sent.", "info")
    else:
        # Insert a new friend request
        cursor.execute(
            "INSERT INTO friend_requests (sender_id, receiver_id) VALUES (%s, %s)",
            (sender_id, receiver_id)
        )
        connection.commit()
        flash("Friend request sent!", "success")

    cursor.close()
    connection.close()
    return redirect(url_for("search_users"))

@app.route("/friend_requests")
def friend_requests():
    """View incoming friend requests."""
    if "user_id" not in session:
        flash("Please log in to view friend requests.", "danger")
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT fr.id, u.username AS sender_username
        FROM friend_requests fr
        JOIN users u ON fr.sender_id = u.id
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
        """,
        (session["user_id"],)
    )
    requests = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("friend_requests.html", requests=requests)

@app.route("/handle_friend_request/<int:request_id>/<string:action>", methods=["POST"])
def handle_friend_request(request_id, action):
    """Accept or reject a friend request."""
    if "user_id" not in session:
        flash("Please log in to manage friend requests.", "danger")
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor()

    if action == "accept":
        cursor.execute(
            "UPDATE friend_requests SET status = 'accepted' WHERE id = %s AND receiver_id = %s",
            (request_id, session["user_id"])
        )
        flash("Friend request accepted!", "success")
    elif action == "reject":
        cursor.execute(
            "UPDATE friend_requests SET status = 'rejected' WHERE id = %s AND receiver_id = %s",
            (request_id, session["user_id"])
        )
        flash("Friend request rejected.", "info")

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("friend_requests"))

# Profile picture update route
@app.route("/update_profile", methods=["GET", "POST"])
def update_profile():
    """Allow users to update their profile picture."""
    if "user_id" not in session:
        flash("Please log in to update your profile.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        profile_picture = request.files.get("profile_picture")

        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            profile_picture.save(file_path)

            # Save the file path to the database
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET profile_picture = %s WHERE id = %s",
                           (f'uploads/profile_pics/{filename}', session['user_id']))
            connection.commit()
            cursor.close()
            connection.close()

            flash("Profile picture updated successfully!", "success")
            return redirect(url_for("profile"))

    return render_template("update_profile.html")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

