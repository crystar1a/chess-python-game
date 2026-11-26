import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path


def normalize_username(username):
    if not isinstance(username, str):
        return None
    name = username.strip()
    return name if re.fullmatch(r'[A-Za-z0-9_.-]{3,20}', name) else None


class UserStore:
    def __init__(self, db_path='server/data/chess.db'):
        if str(db_path) != ':memory:':
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username_lower TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL, password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL, created_at REAL NOT NULL)''')
        self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()


class AuthService:
    def __init__(self, store):
        self.store = store
        self.tokens = {}

    def _user(self, name):
        return self.store.db.execute('SELECT display_name, password_salt, password_hash FROM users WHERE username_lower=?', (name.lower(),)).fetchone()

    def _issue(self, name):
        token = secrets.token_urlsafe(32)
        self.tokens[token] = name
        return {'status': 'ok', 'username': name, 'token': token}

    def check_guest(self, username):
        name = normalize_username(username)
        if name is None:
            return {'status': 'invalid_username'}
        with self.store.lock:
            return {'status': 'username_registered'} if self._user(name) else {'status': 'ok', 'username': name}

    def submit_login_or_probe(self, username, password):
        name = normalize_username(username)
        if name is None:
            return {'status': 'invalid_username'}
        if not isinstance(password, str) or len(password) < 4:
            return {'status': 'invalid_password'}
        with self.store.lock:
            user = self._user(name)
            if user is None:
                return {'status': 'needs_register', 'username': name}
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(user[1]), 200_000).hex()
            return self._issue(user[0]) if hmac.compare_digest(digest, user[2]) else {'status': 'invalid_credentials'}

    def register(self, username, password):
        name = normalize_username(username)
        if name is None:
            return {'status': 'invalid_username'}
        if not isinstance(password, str) or len(password) < 4:
            return {'status': 'invalid_password'}
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200_000).hex()
        with self.store.lock:
            try:
                self.store.db.execute('INSERT INTO users (username_lower, display_name, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)', (name.lower(), name, salt, digest, time.time()))
                self.store.db.commit()
            except sqlite3.IntegrityError:
                return {'status': 'username_registered'}
            return self._issue(name)

    def verify_token(self, token):
        with self.store.lock:
            return self.tokens.get(token) if isinstance(token, str) else None
