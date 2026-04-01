"""
支付回调接口
微信支付和支付宝支付成功后，平台会主动 POST 到这些接口
"""

from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import Order
from services.payment_service import verify_wechat_callback, verify_alipay_callback

router = APIRouter()


def _mark_order_paid(db: Session, out_trade_no: str):
    """通过外部订单号找到订单，标记为已支付"""
    # out_trade_no 格式：NCX{order_id}{timestamp}
    if out_trade_no.startswith("NCX"):
        try:
            order_id = int(out_trade_no[3:].split("1")[0])  # 简单提取
        except Exception:
            return
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.payment_status == "pending":
            order.payment_status = "paid"
            order.paid_at = datetime.utcnow()
            db.commit()


@router.post("/wechat/callback")
async def wechat_callback(request: Request, db: Session = Depends(get_db)):
    """微信支付异步回调"""
    body = await request.body()

    # 解析微信返回的 XML
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(body)
        data = {child.tag: child.text for child in root}
    except Exception:
        return "<xml><return_code>FAIL</return_code><return_msg>解析失败</return_msg></xml>"

    # 验签
    if not verify_wechat_callback(data):
        return "<xml><return_code>FAIL</return_code><return_msg>签名验证失败</return_msg></xml>"

    if data.get("result_code") == "SUCCESS":
        _mark_order_paid(db, data.get("out_trade_no", ""))

    return "<xml><return_code>SUCCESS</return_code><return_msg>OK</return_msg></xml>"


@router.post("/alipay/callback")
async def alipay_callback(request: Request, db: Session = Depends(get_db)):
    """支付宝异步通知"""
    form = await request.form()
    data = dict(form)

    if not verify_alipay_callback(data):
        return "fail"

    if data.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        _mark_order_paid(db, data.get("out_trade_no", ""))

    return "success"
