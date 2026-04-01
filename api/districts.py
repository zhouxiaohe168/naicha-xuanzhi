from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import BusinessDistrict, DistrictAnalysis, Shop, Order, User
from api.deps import get_current_user_optional
from config.settings import MVP_CITY

router = APIRouter()


def user_has_paid(db: Session, user_id: int, district_id: int, product_type: str) -> bool:
    """检查用户是否已购买该商圈的指定报告"""
    # ai_report 同时包含基础报告权限
    allowed_types = ["ai_report"] if product_type == "basic_report" else ["ai_report"]
    if product_type == "basic_report":
        allowed_types = ["basic_report", "ai_report"]

    return db.query(Order).filter(
        Order.user_id == user_id,
        Order.district_id == district_id,
        Order.product_type.in_(allowed_types),
        Order.payment_status == "paid",
    ).first() is not None


@router.get("/cities")
def get_cities():
    return [{"name": MVP_CITY}]


@router.get("/")
def get_districts(
    city: str = Query(default=MVP_CITY),
    db: Session = Depends(get_db),
):
    """商圈列表（免费：名称 + 人流量等级 + 奶茶咖啡总数预览）"""
    districts = db.query(BusinessDistrict).filter(
        BusinessDistrict.city == city
    ).all()

    result = []
    for d in districts:
        item = {
            "id": d.id,
            "name": d.name,
            "foot_traffic_level": d.foot_traffic_level,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        # 附加奶茶/咖啡总数预览（免费可见）
        if d.analysis:
            item["shop_count_preview"] = d.analysis.tea_shop_count + d.analysis.coffee_shop_count
        else:
            item["shop_count_preview"] = None
        result.append(item)

    return result


@router.get("/{district_id}")
def get_district_detail(
    district_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    商圈详情：
    - 未登录 / 未付费 → 返回免费信息 + locked=True
    - 已付费基础报告 → 返回完整分析数据
    - 已付费AI报告 → 同上（AI报告在 /reports 接口单独获取）
    """
    district = db.query(BusinessDistrict).filter(
        BusinessDistrict.id == district_id
    ).first()
    if not district:
        raise HTTPException(status_code=404, detail="商圈不存在")

    # 免费基础信息
    result = {
        "id": district.id,
        "name": district.name,
        "city": district.city,
        "latitude": district.latitude,
        "longitude": district.longitude,
        "foot_traffic_level": district.foot_traffic_level,
        "locked": True,         # 默认锁定
        "has_ai_report": False, # 是否已购 AI 报告
    }

    # 判断付费状态
    paid_basic = False
    paid_ai = False
    if current_user:
        paid_basic = user_has_paid(db, current_user.id, district_id, "basic_report")
        paid_ai = user_has_paid(db, current_user.id, district_id, "ai_report")

    if paid_basic or paid_ai:
        result["locked"] = False
        result["has_ai_report"] = paid_ai

        analysis = db.query(DistrictAnalysis).filter(
            DistrictAnalysis.district_id == district_id
        ).first()

        if analysis:
            result["analysis"] = {
                "tea_shop_count": analysis.tea_shop_count,
                "coffee_shop_count": analysis.coffee_shop_count,
                "brand_distribution": analysis.brand_distribution,
                "surrounding_facilities": analysis.surrounding_facilities,
                "consumption_heat": analysis.consumption_heat,
                "competition_saturation": analysis.competition_saturation,
            }

        shops = db.query(Shop).filter(Shop.district_id == district_id).all()
        result["shops"] = [
            {
                "id": s.id,
                "name": s.name,
                "brand": s.brand,
                "category": s.category,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "address": s.address,
                "rating": s.rating,
            }
            for s in shops
        ]

    return result
