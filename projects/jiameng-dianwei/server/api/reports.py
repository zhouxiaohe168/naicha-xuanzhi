from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import AIReport

router = APIRouter()

# 获取用户已购报告列表
@router.get("/")
def get_reports(db: Session = Depends(get_db)):
    # TODO: 从JWT token获取当前用户ID
    reports = db.query(AIReport).filter(AIReport.user_id == 1).all()
    return [
        {
            "id": r.id,
            "district_id": r.district_id,
            "ai_score": r.ai_score,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]

# 获取单个AI研判报告
@router.get("/{report_id}")
def get_report_detail(report_id: int, db: Session = Depends(get_db)):
    report = db.query(AIReport).filter(AIReport.id == report_id).first()
    if not report:
        return {"error": "报告不存在"}

    return {
        "id": report.id,
        "district_id": report.district_id,
        "ai_score": report.ai_score,
        "recommended_brands": report.recommended_brands,
        "warning_brands": report.warning_brands,
        "estimated_daily_cups": report.estimated_daily_cups,
        "risk_factors": report.risk_factors,
        "site_suggestion": report.site_suggestion,
        "full_report": report.full_report,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
