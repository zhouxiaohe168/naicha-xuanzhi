import random
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt

from models.database import get_db
from models.schemas import User
from config.settings import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    SMS_ACCESS_KEY_ID, SMS_ACCESS_KEY_SECRET, SMS_SIGN_NAME, SMS_TEMPLATE_CODE
)

router = APIRouter()

# ── 内存验证码存储（key: phone, value: {code, expires_at}）──
# 生产环境换 Redis；MVP 用内存足够
_code_store: dict[str, dict] = {}

CODE_EXPIRE_SECONDS = 300  # 5分钟


class SendCodeRequest(BaseModel):
    phone: str

class LoginRequest(BaseModel):
    phone: str
    code: str


def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _send_sms(phone: str, code: str) -> bool:
    """调用阿里云短信发送验证码，返回是否成功"""
    try:
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_dysmsapi20170525 import models as sms_models
        from alibabacloud_tea_openapi import models as open_api_models
        import json

        config = open_api_models.Config(
            access_key_id=SMS_ACCESS_KEY_ID,
            access_key_secret=SMS_ACCESS_KEY_SECRET,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = Client(config)

        request = sms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=SMS_SIGN_NAME,
            template_code=SMS_TEMPLATE_CODE,
            template_param=json.dumps({"code": code}),
        )
        response = client.send_sms(request)
        ok = response.body.code == "OK"
        print(f"[SMS] phone={phone} code={code} result={response.body.code} msg={response.body.message}", flush=True)
        return ok
    except Exception as e:
        print(f"[SMS ERROR] {e}", flush=True)
        return False


# ── 发送验证码 ──────────────────────────────────────────────
@router.post("/send-code")
def send_code(req: SendCodeRequest):
    if not req.phone or len(req.phone) != 11 or not req.phone.isdigit():
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    # 60秒内不重复发送
    existing = _code_store.get(req.phone)
    if existing and time.time() - existing.get("sent_at", 0) < 60:
        raise HTTPException(status_code=429, detail="请勿频繁发送，60秒后再试")

    code = str(random.randint(100000, 999999))

    if SMS_ACCESS_KEY_ID and SMS_TEMPLATE_CODE:
        ok = _send_sms(req.phone, code)
        if not ok:
            raise HTTPException(status_code=500, detail="短信发送失败，请稍后重试")
    else:
        # 未配置短信服务时，打印到日志（开发调试用）
        print(f"[SMS DEBUG] phone={req.phone} code={code}", flush=True)

    _code_store[req.phone] = {
        "code": code,
        "sent_at": time.time(),
        "expires_at": time.time() + CODE_EXPIRE_SECONDS,
    }
    return {"message": "验证码已发送"}


# ── 验证码登录 ──────────────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    entry = _code_store.get(req.phone)

    if not entry:
        raise HTTPException(status_code=400, detail="请先获取验证码")

    if time.time() > entry["expires_at"]:
        _code_store.pop(req.phone, None)
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")

    if entry["code"] != req.code:
        raise HTTPException(status_code=400, detail="验证码错误")

    # 验证成功，清除验证码
    _code_store.pop(req.phone, None)

    # 查找或创建用户
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        user = User(phone=req.phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    return {"token": create_token(user.id), "user_id": user.id}
