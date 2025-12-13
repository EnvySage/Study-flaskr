from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import jsonify
from werkzeug.exceptions import abort

from .auth import login_required
from .db import get_db

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    """Show all the posts, most recent first."""
    db = get_db()
    posts = db.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN users u ON p.author_id = u.user_id"
        " ORDER BY created DESC"
    ).fetchall()
    return render_template("blog/index.html", posts=posts)


def get_post(id, check_author=True):
    """Get a post and its author by id.

    Checks that the id exists and optionally that the current user is
    the author.

    :param id: id of post to get
    :param check_author: require the current user to be the author
    :return: the post with author information
    :raise 404: if a post with the given id doesn't exist
    :raise 403: if the current user isn't the author
    """
    post = (
        get_db()
        .execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN users u ON p.author_id = u.user_id"
        " WHERE p.id = ?",
            (id,),
        )
        .fetchone()
    )

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post["author_id"] != g.user["user_id"]:
        abort(403)

    return post


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new post for the current user."""
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                "INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)",
                (title, body, g.user["user_id"]),
            )
            db.commit()
            return redirect(url_for("blog.index"))

    return render_template("blog/create.html")


@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    """Update a post if the current user is the author."""
    post = get_post(id)

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                "UPDATE post SET title = ?, body = ? WHERE id = ?", (title, body, id)
            )
            db.commit()
            return redirect(url_for("blog.index"))

    return render_template("blog/update.html", post=post)


@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_post(id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("blog.index"))


@bp.route('/profile')
@login_required
def profile():
    """Redirect to user's profile page"""
    return redirect(url_for('blog.user_profile', username=g.user['username']))

@bp.route('/edit_profile', methods=('GET', 'POST'))
@login_required
def edit_profile():
    db = get_db()
    
    if request.method == 'POST':
        # Get form data
        nickname = request.form['nickname']
        bio = request.form['bio']
        contact = request.form['contact']
        
        # Validate inputs
        error = None
        if not nickname:
            error = 'Nickname is required'
        elif len(nickname) < 2 or len(nickname) > 20:
            error = 'Nickname must be between 2 and 20 characters'
        
        if error is None:
            # Check for duplicate nickname
            existing_user = db.execute(
                "SELECT * FROM users WHERE username = ? AND user_id != ?",
                (nickname, g.user['user_id'])
            ).fetchone()
            
            if existing_user:
                error = 'Nickname already taken'
            
        if error is None:
            # Update user info
            db.execute(
                "UPDATE users SET username = ?, bio = ?, contact_info = ? WHERE user_id = ?",
                (nickname, bio, contact, g.user['user_id'])
            )
            db.commit()
            flash('Profile updated successfully!')
            return redirect(url_for('blog.profile'))
        
        flash(error)
    
    # Get current user info
    user = db.execute("SELECT * FROM users WHERE user_id = ?", (g.user['user_id'],)).fetchone()
    
    return render_template('blog/edit_profile.html', user=user)

@bp.route('/user/<username>')
def user_profile(username):
    """Show user profile page for any user"""
    db = get_db()
    
    # Get user info
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    
    if user is None:
        from flask import abort
        abort(404, f"User {username} not found.")
    
    # Get user's recent posts (limit to 5)
    posts = db.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN users u ON p.author_id = u.user_id"
        " WHERE u.username = ?"
        " ORDER BY created DESC"
        " LIMIT 5", (username,)
    ).fetchall()
    
    # Get total post count
    post_count = db.execute(
        "SELECT COUNT(*) FROM post WHERE author_id = ?", (user['user_id'],)
    ).fetchone()[0]
    
    return render_template('blog/user_profile.html', 
                         profile_user=user, 
                         posts=posts, 
                         post_count=post_count)

@bp.route('/check_nickname', methods=('POST',))
@login_required
def check_nickname():
    """Check if nickname is available"""
    nickname = request.form.get('nickname', '').strip()
    
    if not nickname:
        return {'available': False, 'message': '昵称不能为空'}
    
    if len(nickname) < 2 or len(nickname) > 20:
        return {'available': False, 'message': '昵称长度必须在2-20个字符之间'}
    
    db = get_db()
    existing_user = db.execute(
        "SELECT * FROM users WHERE username = ? AND user_id != ?",
        (nickname, g.user['user_id'])
    ).fetchone()
    
    return {'available': existing_user is None}
