import functools
import os
import io
from PIL import Image

from flask import Blueprint, current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask import jsonify  # 新增：支持JSON响应
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")

# 允许的头像文件格式
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


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
                error = f"User {username} is already registered."
            else:
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


# -------------------------- 核心修改：适配前端裁剪的上传接口 --------------------------
@bp.route("/upload_avatar", methods=("POST",))
@login_required
def upload_avatar():
    """
    处理头像上传（适配前端AJAX请求 + 裁剪后的Blob数据）
    返回JSON响应，而非直接重定向
    """
    # 1. 校验文件是否存在
    if 'avatar' not in request.files:
        return jsonify({
            "success": False,
            "message": "未选择图片文件"
        })

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({
            "success": False,
            "message": "请选择要上传的头像图片"
        })

    # 2. 校验文件格式
    filename = secure_filename(file.filename).lower()
    file_ext = os.path.splitext(filename)[1]
    if file_ext not in ['.jpg', '.jpeg', '.png']:
        return jsonify({
            "success": False,
            "message": "仅支持JPG/PNG格式的图片"
        })

    # 3. 校验文件大小（2MB限制）
    if file.content_length and file.content_length > 2 * 1024 * 1024:
        return jsonify({
            "success": False,
            "message": "文件大小不能超过2MB"
        })

    # 4. 确保头像目录存在
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    os.makedirs(avatars_dir, exist_ok=True)

    # 5. 构造用户专属文件名（用user_id命名，覆盖原有头像）
    user_id = str(g.user['user_id'])
    save_filename = f"{user_id}{file_ext}"
    save_path = os.path.join(avatars_dir, save_filename)

    try:
        # 处理裁剪后的图片（统一转为RGB避免PNG透明层问题）
        img = Image.open(file.stream)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB') if file_ext == '.jpg' else img
        # 保存图片（优化压缩，减少体积）
        img.save(save_path, quality=90)

        # 6. 返回成功响应
        return jsonify({
            "success": True,
            "message": "头像上传成功",
            "avatar_url": url_for('static', filename=f'avatars/{save_filename}')
        })

    except Exception as e:
        # 捕获所有异常并返回
        return jsonify({
            "success": False,
            "message": f"上传失败：{str(e)}"
        })


# -------------------------- 保留裁剪接口（可选，若需后端裁剪备用） --------------------------
@bp.route("/crop_avatar", methods=("POST",))
@login_required
def crop_avatar():
    """
    后端裁剪接口（备用，前端已实现裁剪可保留/删除）
    若仅用前端裁剪，此接口可注释
    """
    try:
        # 获取裁剪参数
        x = int(request.form.get('x', 0))
        y = int(request.form.get('y', 0))
        width = int(request.form.get('width', 200))
        height = int(request.form.get('height', 200))

        # 查找用户头像文件
        avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
        user_id = str(g.user['user_id'])
        avatar_path = None
        # 优先找PNG，再找JPG
        for ext in ['.png', '.jpg', '.jpeg']:
            temp_path = os.path.join(avatars_dir, f"{user_id}{ext}")
            if os.path.exists(temp_path):
                avatar_path = temp_path
                break

        if not avatar_path:
            return jsonify({
                "success": False,
                "message": "未找到待裁剪的头像文件"
            })

        # 裁剪并保存
        img = Image.open(avatar_path)
        cropped_img = img.crop((x, y, x + width, y + height))
        cropped_img.save(avatar_path, quality=90)

        return jsonify({
            "success": True,
            "message": "头像裁剪成功"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"裁剪失败：{str(e)}"
        })


# -------------------------- 优化重置头像接口（支持AJAX） --------------------------
@bp.route("/reset_avatar")
@login_required
def reset_avatar():
    """Reset avatar to default（兼容页面跳转和AJAX）"""
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    user_id = str(g.user['user_id'])

    # 删除所有格式的用户头像
    for ext in ['.png', '.jpg', '.jpeg']:
        filepath = os.path.join(avatars_dir, f"{user_id}{ext}")
        if os.path.exists(filepath):
            os.remove(filepath)

    # 判断是否为AJAX请求，返回对应响应
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "message": "头像已恢复为默认"
        })
    else:
        flash('头像已恢复为默认头像')
        return redirect(url_for('blog.user_profile', username=g.user['username']))


# 保留工具函数
def img_crop(img, x, y, width, height):
    """Crop image function"""
    return img.crop((x, y, x + width, y + height))