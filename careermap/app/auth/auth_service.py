"""CareerMap V2.0 Kimlik Doğrulama ve Kullanıcı Yönetim Servisi (Auth Service).
- JWT (JSON Web Token) tabanlı oturum yönetimi.
- bcrypt ile güvenli parola özetleme.
- Aday (Candidate) ve Yönetici (Admin) rollerine dayalı yetkilendirme.
- Varsayılan başlangıç hesapları (Dt. Rümeysa Çolak & Yönetici).
"""
import os
import sqlite3
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("careermap.auth")

SECRET_KEY = os.getenv("CAREERMAP_SECRET_KEY", "careermap-secret-v2-production-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 gün

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Parolayı bcrypt ile güvenli şekilde özetler."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Girilen parolanın bcrypt özetiyle eşleşip eşleşmediğini doğrular."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """JWT erişim belirteci üretir."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """JWT belirtecini çözer ve doğrular."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError as e:
        logger.warning(f"Geçersiz JWT: {e}")
        return None

def init_users_table(conn: sqlite3.Connection):
    """Kullanıcılar tablosunu oluşturur ve varsayılan hesapları ekler."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT DEFAULT 'candidate',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

    # Varsayılan Aday Hesabı: rumeysa@careermap.local / Rumeysa2026!
    cursor.execute("SELECT id FROM users WHERE email = 'rumeysa@careermap.local'")
    if not cursor.fetchone():
        rumeysa_pwd = hash_password("Rumeysa2026!")
        cursor.execute("""
        INSERT INTO users (user_id, email, hashed_password, full_name, role, is_active)
        VALUES ('user-candidate-rumeysa', 'rumeysa@careermap.local', ?, 'Dt. Rümeysa Çolak', 'candidate', 1)
        """, (rumeysa_pwd,))

    # Varsayılan Yönetici Hesabı: admin@careermap.local / Admin2026!
    cursor.execute("SELECT id FROM users WHERE email = 'admin@careermap.local'")
    if not cursor.fetchone():
        admin_pwd = hash_password("Admin2026!")
        cursor.execute("""
        INSERT INTO users (user_id, email, hashed_password, full_name, role, is_active)
        VALUES ('user-admin-system', 'admin@careermap.local', ?, 'Sistem Yöneticisi', 'admin', 1)
        """, (admin_pwd,))

    conn.commit()

def authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> Optional[Dict[str, Any]]:
    """Kullanıcı adı ve parolayı kontrol eder."""
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, email, hashed_password, full_name, role, is_active FROM users WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    if not row:
        return None
    
    user_dict = {
        "user_id": row[0],
        "email": row[1],
        "hashed_password": row[2],
        "full_name": row[3],
        "role": row[4],
        "is_active": row[5]
    }

    if not user_dict["is_active"]:
        return None

    if verify_password(password, user_dict["hashed_password"]):
        return {
            "user_id": user_dict["user_id"],
            "email": user_dict["email"],
            "full_name": user_dict["full_name"],
            "role": user_dict["role"]
        }
    return None

def get_current_user_from_token(token: str, conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """Belirteçten geçerli kullanıcıyı çeker."""
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT user_id, email, full_name, role, is_active FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row or not row[4]:  # is_active
        return None

    return {
        "user_id": row[0],
        "email": row[1],
        "full_name": row[2],
        "role": row[3]
    }

