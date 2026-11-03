"""CareerMap V2.0 Kimlik Doğrulama API Uç Noktaları (Auth API)."""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from ...database.db import get_connection
from ...auth.auth_service import (
    authenticate_user,
    create_access_token,
    hash_password,
    get_current_user_from_token,
    security
)
from ...candidates.profile_manager import CandidateProfileManager

router = APIRouter(prefix="/api/v2/auth", tags=["v2-auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    title: Optional[str] = "Diş Hekimi"
    role: Optional[str] = "candidate"

def get_current_user(credentials = Depends(security)) -> Dict[str, Any]:
    if not credentials or not credentials.credentials:
        # Geliştirme kolaylığı için default rümeysa hesabı dönebilir
        conn = get_connection()
        user = get_current_user_from_token("", conn)
        if user:
            return user
        # Oturum zorunlu ise:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum açılması gerekiyor.")
    
    conn = get_connection()
    user = get_current_user_from_token(credentials.credentials, conn)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz veya süresi dolmuş belirteç.")
    return user

def get_optional_user(credentials = Depends(security)) -> Dict[str, Any]:
    conn = get_connection()
    if credentials and credentials.credentials:
        user = get_current_user_from_token(credentials.credentials, conn)
        if user:
            return user
    # Varsayılan aday kullanıcısı
    return {
        "user_id": "user-candidate-rumeysa",
        "email": "rumeysacolak.dt@gmail.com",
        "full_name": "Dt. Rümeysa Çolak",
        "role": "candidate"
    }

@router.post("/login")
def login(req: LoginRequest):
    """Kullanıcı girişi yapar ve JWT erişim belirteci döner."""
    conn = get_connection()
    user = authenticate_user(conn, req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya parola hatalı."
        )

    token = create_access_token({"sub": user["user_id"], "role": user["role"], "email": user["email"]})
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/register")
def register(req: RegisterRequest):
    """Yeni kullanıcı ve aday profili oluşturur."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),))
    if cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu e-posta adresi zaten kayıtlı.")

    import uuid
    user_id = f"user-{uuid.uuid4().hex[:10]}"
    hashed_pwd = hash_password(req.password)
    role = req.role if req.role in ["candidate", "admin"] else "candidate"

    cursor.execute("""
    INSERT INTO users (user_id, email, hashed_password, full_name, role, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
    """, (user_id, req.email.strip().lower(), hashed_pwd, req.full_name.strip(), role))
    conn.commit()

    if role == "candidate":
        mgr = CandidateProfileManager(conn)
        mgr.upsert_candidate({
            "candidate_id": f"cand-{user_id[-8:]}",
            "user_id": user_id,
            "full_name": req.full_name,
            "title": req.title or "Diş Hekimi",
            "email": req.email,
            "city": "Eskişehir"
        })

    token = create_access_token({"sub": user_id, "role": role, "email": req.email})
    return {
        "status": "success",
        "message": "Hesap başarıyla oluşturuldu.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "email": req.email,
            "full_name": req.full_name,
            "role": role
        }
    }

@router.get("/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Aktif oturum açmış kullanıcı bilgilerini döner."""
    return {"status": "success", "user": user}

