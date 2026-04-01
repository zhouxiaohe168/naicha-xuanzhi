from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import AIReport, Order, BusinessDistrict, DistrictAnalysis, Shop, User
from api.deps import get_current_user
from services.ai_service import generate_ai_report

router = APIRouter()


def _check_ai_paid(db: Session, user_id: int, district_id: int) -> bool:
    return db.query(Order).filter(
        Order.user_id == user_id,
        Order.district_id == district_id,
        Order.product_type == "ai_report",
        Order.payment_status == "paid",
    ).first() is not None


@router.post("/districts/{district_id}/ai-report", tags=["报告"])
async def create_ai_report(
    district_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成 AI 研判报告（需已购买 ai_report）
    - 已有报告则直接返回，不重复生成
    - 调用 Claude API，耗时约 10-30 秒
    """
    # 1. 鉴权：检查是否已付费
    if not _check_ai_paid(db, current_user.id, district_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先购买AI研判报告")

    # 2. 已有报告直接返回（幂等）
    existing = db.query(AIReport).filter(
        AIReport.user_id == current_user.id,
        AIReport.district_id == district_id,
    ).first()
    if existing:
        return _format_report(existing)

    # 3. 取商圈数据
    district = db.query(BusinessDistrict).filter(BusinessDistrict.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="商圈不存在")

    analysis = db.query(DistrictAnalysis).filter(DistrictAnalysis.district_id == district_id).first()
    shops = db.query(Shop).filter(Shop.district_id == district_id).all()

    district_dict = {
        "name": district.name, "city": district.city,
        "foot_traffic_level": district.foot_traffic_level,
    }
    analysis_dict = {
        "tea_shop_count": analysis.tea_shop_count if analysis else 0,
        "coffee_shop_count": analysis.coffee_shop_count if analysis else 0,
        "brand_distribution": analysis.brand_distribution if analysis else {},
        "surrounding_facilities": analysis.surrounding_facilities if analysis else {},
        "consumption_heat": analysis.consumption_heat if analysis else "medium",
    } if analysis else {}
    shops_list = [{"name": s.name, "brand": s.brand, "category": s.category} for s in shops]

    # 4. 调用 Claude API
    try:
        result = await generate_ai_report(district_dict, analysis_dict, shops_list)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 5. 存库
    report = AIReport(
        district_id=district_id,
        user_id=current_user.id,
        ai_score=result.get("ai_score", 0),
        recommended_brands=result.get("recommended_brands", []),
        warning_brands=result.get("warning_brands", []),
        estimated_daily_cups=result.get("analysis", {}).get("daily_cups", ""),
        risk_factors=result.get("risks", []),
        site_suggestion=result.get("suggestion", ""),
        full_report=str(result),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return _format_report(report)


@router.get("/")
def get_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户已购报告列表（AI报告 + 基础报告订单合并）"""
    # AI 报告
    ai_reports = db.query(AIReport).filter(AIReport.user_id == current_user.id).all()
    ai_district_ids = {r.district_id for r in ai_reports}

    # 基础报告订单
    basic_orders = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.product_type == "basic_report",
        Order.payment_status == "paid",
    ).all()

    result = []

    # AI 报告
    for r in ai_reports:
        district = db.query(BusinessDistrict).filter(BusinessDistrict.id == r.district_id).first()
        result.append({
            "id": r.id,
            "type": "ai_report",
            "district_id": r.district_id,
            "district_name": district.name if district else "未知商圈",
            "ai_score": r.ai_score,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    # 基础报告（去掉已有 AI 报告的商圈）
    for o in basic_orders:
        if o.district_id not in ai_district_ids:
            district = db.query(BusinessDistrict).filter(BusinessDistrict.id == o.district_id).first()
            result.append({
                "id": o.id,
                "type": "basic_report",
                "district_id": o.district_id,
                "district_name": district.name if district else "未知商圈",
                "ai_score": None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

    return sorted(result, key=lambda x: x["created_at"] or "", reverse=True)


@router.get("/{report_id}")
def get_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个 AI 研判报告详情"""
    report = db.query(AIReport).filter(
        AIReport.id == report_id,
        AIReport.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return _format_report(report)


def _format_report(r: AIReport) -> dict:
    return {
        "id": r.id,
        "district_id": r.district_id,
        "ai_score": r.ai_score,
        "recommended_brands": r.recommended_brands,
        "warning_brands": r.warning_brands,
        "estimated_daily_cups": r.estimated_daily_cups,
        "risk_factors": r.risk_factors,
        "site_suggestion": r.site_suggestion,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
