"""
探铺订单与支付接口
- 无需注册，直接购买
- 支持支付宝H5支付
- 支持 mock 模式（测试用）
"""

import uuid
import hashlib
import time
import json
import urllib.parse
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

from config.settings import (
    PRICE_BASIC, PRICE_AI, PRICE_OPPORTUNITY,
    ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY, ALIPAY_PUBLIC_KEY,
    ALIPAY_NOTIFY_URL, ALIPAY_RETURN_URL, FRONTEND_URL,
)

router = APIRouter()

# 内存订单存储（MVP阶段，生产环境应用数据库）
# key: order_id, value: {status, amount, product, report_data, created_at}
_orders: dict = {}


class CreateOrderRequest(BaseModel):
    product_type: str       # basic | ai | opportunity
    brand: str
    city: str
    report_data: Optional[dict] = None   # wizard已生成的报告数据（缓存）
    opportunity_id: Optional[str] = None  # 机会集市解锁时用
    contact: Optional[str] = None         # 邮箱或手机（可选）


def _price_for_product(product_type: str) -> int:
    """返回分为单位的价格"""
    mapping = {
        "basic": PRICE_BASIC,
        "ai": PRICE_AI,
        "opportunity": PRICE_OPPORTUNITY,
    }
    return mapping.get(product_type, PRICE_AI)


def _price_yuan(product_type: str) -> str:
    """返回元为单位的价格字符串"""
    return f"{_price_for_product(product_type) / 100:.2f}"


def _gen_order_id() -> str:
    """生成唯一订单号"""
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:6].upper()
    return f"TP{ts}{uid}"


# ─── 创建订单 ───────────────────────────────────────────

@router.post("/order")
async def create_order(req: CreateOrderRequest):
    """创建订单，返回支付信息"""
    if req.product_type not in ("basic", "ai", "opportunity"):
        raise HTTPException(status_code=400, detail="无效的产品类型")

    order_id = _gen_order_id()
    amount = _price_for_product(req.product_type)

    _orders[order_id] = {
        "order_id": order_id,
        "status": "pending",
        "product_type": req.product_type,
        "brand": req.brand,
        "city": req.city,
        "amount": amount,
        "contact": req.contact,
        "report_data": req.report_data,
        "opportunity_id": req.opportunity_id,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
    }

    response = {
        "order_id": order_id,
        "amount": amount,
        "amount_yuan": f"{amount / 100:.2f}",
        "product_type": req.product_type,
    }

    # 生产环境：生成支付宝H5支付链接
    if ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY:
        pay_url = _alipay_h5_url(order_id, amount, req.brand, req.city, req.product_type)
        response["pay_url"] = pay_url
        response["payment_method"] = "alipay"
    else:
        # 开发/测试：mock支付，直接标记为已支付
        response["pay_url"] = None
        response["payment_method"] = "mock"
        response["mock_confirm_url"] = f"/api/checkout/mock-pay/{order_id}"

    return response


# ─── Mock 支付（开发测试用）─────────────────────────────

@router.post("/mock-pay/{order_id}")
async def mock_pay(order_id: str):
    """开发测试用：直接标记订单为已支付"""
    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order["status"] == "paid":
        return {"order_id": order_id, "status": "paid"}

    order["status"] = "paid"
    order["paid_at"] = datetime.utcnow().isoformat()
    return {"order_id": order_id, "status": "paid", "message": "支付成功（测试）"}


# ─── 查询订单状态 ────────────────────────────────────────

@router.get("/order/{order_id}")
async def get_order(order_id: str):
    """查询订单状态，已支付则返回报告数据"""
    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    result = {
        "order_id": order_id,
        "status": order["status"],
        "product_type": order["product_type"],
        "brand": order["brand"],
        "city": order["city"],
        "amount_yuan": f"{order['amount'] / 100:.2f}",
    }

    if order["status"] == "paid":
        # 已付款：返回报告数据
        result["report_data"] = order.get("report_data")
        result["opportunity_id"] = order.get("opportunity_id")

    return result


# ─── 支付宝回调 ─────────────────────────────────────────

@router.post("/payment/alipay/notify")
async def alipay_notify(request: Request):
    """支付宝异步通知回调"""
    form = await request.form()
    data = dict(form)

    if not _verify_alipay_sign(data):
        return "fail"

    trade_status = data.get("trade_status", "")
    out_trade_no = data.get("out_trade_no", "")

    if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        order = _orders.get(out_trade_no)
        if order and order["status"] == "pending":
            order["status"] = "paid"
            order["paid_at"] = datetime.utcnow().isoformat()
            order["alipay_trade_no"] = data.get("trade_no", "")

    return "success"


@router.get("/payment/alipay/return")
async def alipay_return(request: Request):
    """支付宝同步跳转回调（用户支付后跳转回来）"""
    params = dict(request.query_params)
    out_trade_no = params.get("out_trade_no", "")

    # 简单验签
    if _verify_alipay_sign(params):
        order = _orders.get(out_trade_no)
        if order:
            order["status"] = "paid"
            order["paid_at"] = datetime.utcnow().isoformat()

    # 跳转到前端报告页
    return_url = f"{FRONTEND_URL}/report?order_id={out_trade_no}"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=return_url)


# ─── 支付宝签名工具 ──────────────────────────────────────

def _alipay_h5_url(order_id: str, amount: int, brand: str, city: str, product_type: str) -> str:
    """生成支付宝H5支付链接"""
    product_labels = {"basic": "位置信息包", "ai": "AI深度报告", "opportunity": "机会解锁"}
    subject = f"探铺-{product_labels.get(product_type, '报告')}-{brand}{city}"
    amount_yuan = f"{amount / 100:.2f}"

    biz_content = json.dumps({
        "out_trade_no": order_id,
        "total_amount": amount_yuan,
        "subject": subject,
        "product_code": "QUICK_WAP_WAY",
    }, ensure_ascii=False)

    params = {
        "app_id": ALIPAY_APP_ID,
        "method": "alipay.trade.wap.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": ALIPAY_NOTIFY_URL,
        "return_url": ALIPAY_RETURN_URL + f"?order_id={order_id}",
        "biz_content": biz_content,
    }

    sign = _rsa2_sign(params)
    params["sign"] = sign

    gateway = "https://openapi.alipay.com/gateway.do"
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{gateway}?{query}"


def _rsa2_sign(params: dict) -> str:
    """RSA2签名"""
    if not ALIPAY_PRIVATE_KEY:
        return "mock_sign"
    try:
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        import base64

        # 排序并拼接
        sorted_params = sorted((k, v) for k, v in params.items() if k != "sign")
        sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)

        # 加载私钥
        key_pem = ALIPAY_PRIVATE_KEY
        if not key_pem.startswith("-----"):
            key_pem = f"-----BEGIN RSA PRIVATE KEY-----\n{key_pem}\n-----END RSA PRIVATE KEY-----"
        key = RSA.import_key(key_pem)

        h = SHA256.new(sign_str.encode("utf-8"))
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        print(f"[ALIPAY] sign error: {e}")
        return "sign_error"


def _verify_alipay_sign(params: dict) -> bool:
    """验证支付宝回调签名"""
    if not ALIPAY_PUBLIC_KEY:
        return True  # 未配置时信任回调（仅开发）
    try:
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        import base64

        sign = params.get("sign", "")
        sorted_params = sorted(
            (k, v) for k, v in params.items()
            if k not in ("sign", "sign_type")
        )
        sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)

        key_pem = ALIPAY_PUBLIC_KEY
        if not key_pem.startswith("-----"):
            key_pem = f"-----BEGIN PUBLIC KEY-----\n{key_pem}\n-----END PUBLIC KEY-----"
        key = RSA.import_key(key_pem)

        h = SHA256.new(sign_str.encode("utf-8"))
        pkcs1_15.new(key).verify(h, base64.b64decode(sign))
        return True
    except Exception:
        return False
