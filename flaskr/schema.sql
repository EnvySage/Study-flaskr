-- 创建用户表 (users)
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500) DEFAULT 'default_avatar.png',
    bio TEXT DEFAULT '',
    contact_info VARCHAR(200) DEFAULT '',
    registration_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_time DATETIME NULL
);

-- 创建用户作品表 (user_works)
CREATE TABLE IF NOT EXISTS user_works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NULL,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(user_id)
);

-- 创建个人资料修改记录表 (profile_change_log)
CREATE TABLE IF NOT EXISTS profile_change_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    changed_field VARCHAR(50) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    change_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    change_source VARCHAR(20) DEFAULT 'user',
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
