from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt

from models.database import get_db
from models.schemas import User
from config.settings import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

# 请求模型
class RegisterRequest(BaseModel):
    phone: str

class LoginRequest(BaseModel):
    phone: str
    code: str  # 验证码

# 生成JWT token
def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    data = {"sub": str(user_id), "exp": expire}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# 发送验证码
@router.post("/send-code")
def send_code(req: RegisterRequest, db: Session = Depends(get_db)):
    # TODO: 调用阿里云短信服务发送验证码
    # 临时：任何手机号都返回成功
    return {"message": "验证码已发送"}

# 手机号+验证码登录（新用户自动注册）
@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # TODO: 验证短信验证码
    # 临时：验证码为 123456 即可登录
    if req.code != "123456":
        raise HTTPException(status_code=400, detail="验证码错误")

    # 查找或创建用户
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        user = User(phone=req.phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_token(user.id)
    return {"token": token, "user_id": user.id}
