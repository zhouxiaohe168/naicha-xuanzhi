from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.database import Base

# ========== 用户表 ==========
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True)          # 手机号
    wechat_openid = Column(String(100), unique=True, nullable=True)  # 微信OpenID
    nickname = Column(String(50), default="")                     # 昵称
    created_at = Column(DateTime, server_default=func.now())      # 注册时间

    orders = relationship("Order", back_populates="user")

# ========== 商圈表 ==========
class BusinessDistrict(Base):
    __tablename__ = "business_districts"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(50), index=True)                         # 城市
    name = Column(String(100))                                    # 商圈名称
    latitude = Column(Float)                                      # 纬度
    longitude = Column(Float)                                     # 经度
    foot_traffic_level = Column(String(10), default="medium")     # 人流量等级：high/medium/low
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    shops = relationship("Shop", back_populates="district")
    analysis = relationship("DistrictAnalysis", back_populates="district", uselist=False)

# ========== 门店表 ==========
class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("business_districts.id"))  # 所属商圈
    name = Column(String(200))                                    # 店名
    brand = Column(String(100))                                   # 品牌名
    category = Column(String(20))                                 # 分类：tea（奶茶）/ coffee（咖啡）
    latitude = Column(Float)                                      # 纬度
    longitude = Column(Float)                                     # 经度
    address = Column(String(300))                                 # 详细地址
    rating = Column(Float, default=0)                             # 评分
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    district = relationship("BusinessDistrict", back_populates="shops")

# ========== 商圈分析表 ==========
class DistrictAnalysis(Base):
    __tablename__ = "district_analysis"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("business_districts.id"), unique=True)
    tea_shop_count = Column(Integer, default=0)                   # 奶茶店数量
    coffee_shop_count = Column(Integer, default=0)                # 咖啡店数量
    brand_distribution = Column(JSON, default={})                 # 品牌分布
    surrounding_facilities = Column(JSON, default={})             # 周边配套
    consumption_heat = Column(String(10), default="medium")       # 消费热度
    competition_saturation = Column(String(10), default="medium") # 竞争饱和度
    analysis_date = Column(DateTime, server_default=func.now())

    district = relationship("BusinessDistrict", back_populates="analysis")

# ========== AI研判报告表 ==========
class AIReport(Base):
    __tablename__ = "ai_reports"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("business_districts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    ai_score = Column(Integer)                                    # AI评分 1-100
    recommended_brands = Column(JSON, default=[])                 # 推荐品牌
    warning_brands = Column(JSON, default=[])                     # 预警品牌
    estimated_daily_cups = Column(String(50))                     # 预估日均杯数
    risk_factors = Column(JSON, default=[])                       # 风险因素
    site_suggestion = Column(Text)                                # 选址建议
    full_report = Column(Text)                                    # 完整报告内容
    created_at = Column(DateTime, server_default=func.now())

# ========== 订单表 ==========
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    district_id = Column(Integer, ForeignKey("business_districts.id"))
    amount = Column(Float)                                        # 金额
    product_type = Column(String(20))                             # 产品类型：basic_report / ai_report
    payment_method = Column(String(20))                           # 支付方式：wechat / alipay
    payment_status = Column(String(20), default="pending")        # 支付状态：pending / paid / failed
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
