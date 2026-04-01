from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import get_db
from models.schemas import Order
from config.settings import PRICE_BASIC, PRICE_AI

router = APIRouter()

class CreateOrderRequest(BaseModel):
    district_id: int
    product_type: str      # basic_report / ai_report
    payment_method: str    # wechat / alipay

# 创建订单
@router.post("/")
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    # 确定价格
    amount = PRICE_BASIC if req.product_type == "basic_report" else PRICE_AI

    order = Order(
        user_id=1,  # TODO: 从JWT token获取当前用户ID
        district_id=req.district_id,
        amount=amount,
        product_type=req.product_type,
        payment_method=req.payment_method,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # TODO: 调用微信/支付宝创建支付订单，返回支付参数
    return {
        "order_id": order.id,
        "amount": amount,
        "payment_url": "https://pay.example.com/mock",  # 临时mock
    }

# 获取用户订单列表
@router.get("/")
def get_orders(db: Session = Depends(get_db)):
    # TODO: 从JWT token获取当前用户ID
    orders = db.query(Order).filter(Order.user_id == 1).all()
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
