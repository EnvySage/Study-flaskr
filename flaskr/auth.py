import functools

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = (
            get_db().execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        )


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Register a new user.

    Validates that the username is not already taken. Hashes the
    password for security.
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone():
            error = "Username already exists. Please choose another one."

        if error is None:
            try:
                db.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                # The username was already taken, which caused the
                # commit to fail. Show a validation error.
                error = f"User {username} is already registered."
            else:
                # Success, go to the login page.
                return redirect(url_for("auth.login"))

        flash(error)

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Log in a registered user by adding the user id to the session."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            # store the user id in a new session and return to the index
            session.clear()
            session["user_id"] = user["user_id"]
            return redirect(url_for("index"))

        flash(error)

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for("index"))

@bp.route("/upload_avatar", methods=("POST",))
@login_required
def upload_avatar():
    """Upload avatar for current user"""
    if 'avatar' not in request.files:
        flash('No file uploaded')
        return redirect(url_for('blog.user_profile', username=g.user['username']))
    
    file = request.files['avatar']
    if file.filename == '' or file.content_length == 0:
        flash('No file selected')
        return redirect(url_for('blog.user_profile', username=g.user['username']))
    
    # Check file extension
    filename = file.filename.lower()
    if not (filename.endswith('.jpg') or filename.endswith('.png')):
        flash('Only JPG and PNG files are allowed')
        return redirect(url_for('blog.user_profile', username=g.user['username']))
    
    # Check file size (2MB limit)
    if file.content_length > 2 * 1024 * 1024:
        flash('File size must be less than 2MB')
        return redirect(url_for('blog.user_profile', username=g.user['username']))
    
    # Save file to static directory
    import os
    from werkzeug.utils import secure_filename
    
    # Create avatars directory if it doesn't exist
    import os
    from flask import current_app
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    if not os.path.exists(avatars_dir):
        os.makedirs(avatars_dir)
    
    # Save file with user id as filename
    filename = secure_filename(file.filename)
    filepath = os.path.join(avatars_dir, str(g.user['user_id']) + '.png')
    
    # Convert to PNG format
    from PIL import Image
    try:
        img = Image.open(file.stream)
        img = img.convert('RGBA')
        img.save(filepath, 'PNG')
    except Exception as e:
        flash('Error processing image: ' + str(e))
        return redirect(url_for('blog.user_profile', username=g.user['username']))
    
    flash('Avatar uploaded successfully!')
    return redirect(url_for('blog.user_profile', username=g.user['username']))

@bp.route("/crop_avatar", methods=("POST",))
@login_required
def crop_avatar():
    """Crop avatar for current user"""
    # Get crop parameters from form
    x = int(request.form.get('x', 0))
    y = int(request.form.get('y', 0))
    width = int(request.form.get('width', 200))
    height = int(request.form.get('height', 200))
    
    # Open the avatar image
    import os
    from PIL import Image
    from flask import current_app
    
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    filepath = os.path.join(avatars_dir, str(g.user['user_id']) + '.png')
    
    try:
        img = Image.open(filepath)
        # Crop the image
        cropped_img = img.crop((x, y, x + width, y + height))
        # Save the cropped image
        cropped_img.save(filepath, 'PNG')
        flash('Avatar cropped successfully!')
    except Exception as e:
        flash('Error cropping image: ' + str(e))
    
    return redirect(url_for('blog.user_profile', username=g.user['username']))

def img_crop(img, x, y, width, height):
    """Crop image function"""
    return img.crop((x, y, x + width, y + height))

@bp.route("/reset_avatar")
@login_required
def reset_avatar():
    """Reset avatar to default"""
    import os
    from flask import current_app
    
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    filepath = os.path.join(avatars_dir, str(g.user['user_id']) + '.png')
    
    # Remove the custom avatar file if it exists
    if os.path.exists(filepath):
        os.remove(filepath)
    
    flash('头像已恢复为默认头像')
    return redirect(url_for('blog.user_profile', username=g.user['username']))
