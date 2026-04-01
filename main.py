from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import PROJECT_NAME, VERSION
from models.database import engine, Base
from api.auth import router as auth_router
from api.districts import router as districts_router
from api.orders import router as orders_router
from api.reports import router as reports_router

# 创建所有表
Base.metadata.create_all(bind=engine)

# 初始化应用
app = FastAPI(title=PROJECT_NAME, version=VERSION)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(districts_router, prefix="/api/districts", tags=["商圈"])
app.include_router(orders_router, prefix="/api/orders", tags=["订单"])
app.include_router(reports_router, prefix="/api/reports", tags=["报告"])

@app.get("/api/health")
def health_check():
    return {"status": "ok", "project": PROJECT_NAME, "version": VERSION}
