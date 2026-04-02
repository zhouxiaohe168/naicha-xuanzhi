from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.settings import PROJECT_NAME, VERSION
from models.database import engine, Base, SessionLocal
from api.auth import router as auth_router
from api.districts import router as districts_router
from api.orders import router as orders_router
from api.reports import router as reports_router, create_ai_report
from api.payment import router as payment_router
from api.analyze import router as analyze_router
from api.wizard import router as wizard_router
from api.checkout import router as checkout_router
from api.market_api import router as market_router
from data_collector.seeder import seed_districts
from data_collector.analyzer import run_full_collection

# 创建所有表
Base.metadata.create_all(bind=engine)

# 定时任务调度器
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def weekly_collection_job():
    """每周自动采集任务"""
    db = SessionLocal()
    try:
        await run_full_collection(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化商圈数据
    db = SessionLocal()
    try:
        seed_districts(db)
    finally:
        db.close()

    # 启动定时任务（每周一凌晨3点执行）
    scheduler.add_job(weekly_collection_job, "cron", day_of_week="mon", hour=3)
    scheduler.start()
    print(f"[{PROJECT_NAME}] 服务启动，定时采集任务已注册")

    yield

    scheduler.shutdown()


# 初始化应用
app = FastAPI(title=PROJECT_NAME, version=VERSION, lifespan=lifespan, redirect_slashes=False)

# 跨域配置（所有域名白名单）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "https://tanpuai.com",
        "https://www.tanpuai.com",
        "https://naichaxuanzhi.com",
        "https://www.naichaxuanzhi.com",
        "https://tanpu.vercel.app",
        "https://www.tanpu.app",
        "https://tanpu.app",
        "https://client-five-flame-97.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 旧路由（向后兼容） ──────────────────────────────────
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(districts_router, prefix="/api/districts", tags=["商圈"])
app.include_router(orders_router, prefix="/api/orders", tags=["订单"])
app.include_router(reports_router, prefix="/api/reports", tags=["报告"])
app.add_api_route("/api/districts/{district_id}/ai-report", create_ai_report, methods=["POST"], tags=["报告"])
app.include_router(payment_router, prefix="/api/payment", tags=["支付"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["选址分析"])

# ── 新路由（探铺 v2） ────────────────────────────────────
app.include_router(wizard_router, prefix="/api/wizard", tags=["品牌研判向导"])
app.include_router(checkout_router, prefix="/api/checkout", tags=["订单支付"])
app.include_router(market_router, prefix="/api/market", tags=["机会集市"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "project": PROJECT_NAME, "version": VERSION}


@app.post("/api/admin/collect", tags=["管理"])
async def manual_collect():
    """手动触发全量数据采集（管理用）"""
    db = SessionLocal()
    try:
        await run_full_collection(db)
        return {"status": "ok", "message": "采集完成"}
    finally:
        db.close()
