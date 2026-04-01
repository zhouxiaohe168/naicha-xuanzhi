from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import BusinessDistrict, DistrictAnalysis, Shop
from config.settings import MVP_CITY

router = APIRouter()

# 获取城市列表
@router.get("/cities")
def get_cities():
    # MVP只有一个城市
    return [{"name": MVP_CITY}]

# 获取商圈列表（免费信息）
@router.get("/")
def get_districts(
    city: str = Query(default=MVP_CITY),
    db: Session = Depends(get_db)
):
    districts = db.query(BusinessDistrict).filter(
        BusinessDistrict.city == city
    ).all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "foot_traffic_level": d.foot_traffic_level,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in districts
    ]

# 获取商圈详情（根据是否付费返回不同内容）
@router.get("/{district_id}")
def get_district_detail(
    district_id: int,
    range_meters: int = Query(default=1000, description="分析范围（米）"),
    db: Session = Depends(get_db)
):
    district = db.query(BusinessDistrict).filter(
        BusinessDistrict.id == district_id
    ).first()
    if not district:
        return {"error": "商圈不存在"}

    # 基础信息（免费）
    result = {
        "id": district.id,
        "name": district.name,
        "city": district.city,
        "foot_traffic_level": district.foot_traffic_level,
        "latitude": district.latitude,
        "longitude": district.longitude,
    }

    # TODO: 根据用户是否付费，返回详细分析数据
    # 这里先返回完整数据用于演示
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

    # 门店列表
    shops = db.query(Shop).filter(Shop.district_id == district_id).all()
    result["shops"] = [
        {
            "id": s.id,
            "name": s.name,
            "brand": s.brand,
            "category": s.category,
            "address": s.address,
            "rating": s.rating,
        }
        for s in shops
    ]

    return result
