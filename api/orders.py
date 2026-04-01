from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from models.database import get_db
from models.schemas import Order, User
from api.deps import get_current_user
from config.settings import PRICE_BASIC, PRICE_AI

router = APIRouter()


class CreateOrderRequest(BaseModel):
    district_id: int
    product_type: str    # basic_report / ai_report
    payment_method: str  # wechat / alipay / mock


@router.post("/")
def create_order(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建支付订单"""
    if req.product_type not in ("basic_report", "ai_report"):
        raise HTTPException(status_code=400, detail="无效的产品类型")

    amount = PRICE_BASIC if req.product_type == "basic_report" else PRICE_AI

    # 检查是否已购买（防重复付款）
    existing = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.district_id == req.district_id,
        Order.product_type == req.product_type,
        Order.payment_status == "paid",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="您已购买过该报告")

    order = Order(
        user_id=current_user.id,
        district_id=req.district_id,
        amount=amount,
        product_type=req.product_type,
        payment_method=req.payment_method,
        payment_status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # MVP阶段：mock支付直接跳过支付环节，立即标记为 paid
    if req.payment_method == "mock":
        order.payment_status = "paid"
        order.paid_at = datetime.utcnow()
        db.commit()
        return {"order_id": order.id, "status": "paid", "amount": amount}

    # 真实支付（M5再接入微信/支付宝）
    return {
        "order_id": order.id,
        "status": "pending",
        "amount": amount,
        "payment_url": "https://pay.example.com/pending",  # M5替换
    }


@router.get("/")
def get_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户订单列表"""
    orders = db.query(Order).filter(Order.user_id == current_user.id).all()
    return [
        {
            "id": o.id,
            "district_id": o.district_id,
            "amount": o.amount,
            "product_type": o.product_type,
            "payment_status": o.payment_status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]
