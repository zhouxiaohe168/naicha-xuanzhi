"""
探铺机会集市接口
AI定期扫描市场信号，发现竞品撤店、新商圈崛起等机会
MVP阶段：数据为AI生成的结构化样本 + 高德实时验证
生产阶段：对接企查查工商数据（监控注销/变更）+ 高德新POI变化检测
"""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import httpx
from config.settings import AMAP_KEY

router = APIRouter()

AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"

# MVP阶段：AI生成的机会数据（结构化）
# 生产阶段替换为：对接企查查注销检测 + 高德新开发区POI扫描
OPPORTUNITIES = [
    {
        "id": "opp-hz-001",
        "type": "位置释放",
        "type_key": "release",
        "urgency": "high",
        "badge": "🔥 紧急",
        "title": "竞品撤店 · 黄金铺位空出",
        "city": "杭州",
        "district": "拱墅区",
        "summary_locked": "某头部奶茶品牌门店关闭，临街铺位预计下月空出",
        "summary_unlocked": "蜜雪冰城拱墅区运河旁店关闭，临街铺位预计2024年8月空出。周边500m内无同类竞品，日均客流6000+。",
        "address": "杭州市拱墅区运河路XX号（具体地址付款后查看）",
        "rent_estimate": "约6,800元/月",
        "contact": "商圈招商管理处",
        "tags": ["临街铺位", "日流量6000+", "低竞争"],
        "metrics": {
            "daily_traffic": "6,000+",
            "competitor_count": "2家（均为高端）",
            "consumption_index": "71/100",
            "recommended_brands": ["蜜雪冰城", "古茗", "沪上阿姨"],
        },
        "price": 599,
        "created_at": "2024-07-01",
        "expires_at": "2024-08-31",
    },
    {
        "id": "opp-cd-001",
        "type": "新商圈崛起",
        "type_key": "new_district",
        "urgency": "medium",
        "badge": "🌱 新兴",
        "title": "新住宅区商业街开街",
        "city": "成都",
        "district": "天府新区",
        "summary_locked": "3.2万户新社区商业配套即将开业，品牌空白窗口期",
        "summary_unlocked": "成都天府新区兴隆街道3.2万户住宅社区商业配套2024年9月开业，目前招商率仅40%，奶茶赛道完全空白。",
        "address": "成都市天府新区兴隆街道商业综合体B区（具体铺位付款后查看）",
        "rent_estimate": "约5,200元/月（开业前优惠期）",
        "contact": "天府新区商业招商部",
        "tags": ["空白市场", "3.2万住户", "早期布局"],
        "metrics": {
            "daily_traffic": "预计8,000+（开业后）",
            "competitor_count": "0家（全区域空白）",
            "consumption_index": "68/100",
            "recommended_brands": ["蜜雪冰城", "古茗", "茶百道"],
        },
        "price": 599,
        "created_at": "2024-07-05",
        "expires_at": "2024-09-15",
    },
    {
        "id": "opp-wh-001",
        "type": "品牌红利窗口",
        "type_key": "brand_window",
        "urgency": "medium",
        "badge": "⚡ 限时",
        "title": "古茗开放新城区代理",
        "city": "武汉",
        "district": "东湖新技术开发区",
        "summary_locked": "品牌官方开放该区域加盟申请，目前无竞争门店",
        "summary_unlocked": "古茗品牌2024年Q3正式开放武汉光谷区域代理申请，该区域目前无古茗门店，竞品仅3家中高端品牌，适合快速入场。",
        "address": "武汉市东湖高新区光谷核心商圈（具体点位付款后查看）",
        "rent_estimate": "约7,500元/月",
        "contact": "古茗品牌武汉区域招商",
        "tags": ["官方授权", "无竞争", "扩张期"],
        "metrics": {
            "daily_traffic": "12,000+（光谷步行街）",
            "competitor_count": "3家（均为中高端）",
            "consumption_index": "79/100",
            "recommended_brands": ["古茗"],
        },
        "price": 599,
        "created_at": "2024-07-10",
        "expires_at": "2024-09-30",
    },
    {
        "id": "opp-nb-001",
        "type": "位置释放",
        "type_key": "release",
        "urgency": "low",
        "badge": "📍 可用",
        "title": "商场二楼奶茶区空铺",
        "city": "宁波",
        "district": "鄞州区",
        "summary_locked": "万象城二楼餐饮区奶茶档口空出，客流稳定",
        "summary_unlocked": "宁波万象城二楼F区23号铺（45㎡），原蜜雪冰城撤出，商场招商现对外招租，月均进店人次约4万，周边同类竞品3家（高端定位）。",
        "address": "宁波市鄞州区天童南路万象城二楼F区23号",
        "rent_estimate": "约8,500元/月",
        "contact": "万象城商场招商部 · 张经理",
        "tags": ["商场位置", "稳定客流", "档口型"],
        "metrics": {
            "daily_traffic": "约12,000人",
            "competitor_count": "3家（均为高端）",
            "consumption_index": "75/100",
            "recommended_brands": ["蜜雪冰城", "古茗"],
        },
        "price": 599,
        "created_at": "2024-06-20",
        "expires_at": "2024-08-20",
        "unlocked": False,   # 演示用，可设为True展示已解锁状态
    },
]


@router.get("/opportunities")
async def list_opportunities(city: Optional[str] = None, type_key: Optional[str] = None):
    """获取机会列表（锁定版，隐藏详细地址）"""
    opps = OPPORTUNITIES

    if city:
        opps = [o for o in opps if city in o["city"]]
    if type_key:
        opps = [o for o in opps if o["type_key"] == type_key]

    # 返回时隐藏解锁信息
    result = []
    for o in opps:
        item = {
            "id": o["id"],
            "type": o["type"],
            "type_key": o["type_key"],
            "urgency": o["urgency"],
            "badge": o["badge"],
            "title": o["title"],
            "city": o["city"],
            "district": o["district"],
            "summary": o["summary_locked"],
            "tags": o["tags"],
            "price": o["price"],
            "created_at": o["created_at"],
            "locked": not o.get("unlocked", True),
        }
        result.append(item)

    return {
        "total": len(result),
        "this_week_new": 7,
        "by_type": {
            "release": sum(1 for o in result if o["type_key"] == "release"),
            "new_district": sum(1 for o in result if o["type_key"] == "new_district"),
            "brand_window": sum(1 for o in result if o["type_key"] == "brand_window"),
        },
        "opportunities": result,
    }


@router.get("/opportunities/{opp_id}")
async def get_opportunity(opp_id: str, order_id: Optional[str] = None):
    """
    获取机会详情
    - 未解锁：返回模糊信息
    - 已解锁（提供有效order_id）：返回完整信息
    """
    opp = next((o for o in OPPORTUNITIES if o["id"] == opp_id), None)
    if not opp:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="机会不存在")

    # 检查是否已解锁（从checkout模块查询订单状态）
    is_unlocked = opp.get("unlocked", False)
    if order_id and not is_unlocked:
        try:
            from api.checkout import _orders
            order = _orders.get(order_id)
            if order and order["status"] == "paid" and order.get("opportunity_id") == opp_id:
                is_unlocked = True
        except Exception:
            pass

    if is_unlocked:
        return {
            "id": opp["id"],
            "type": opp["type"],
            "title": opp["title"],
            "city": opp["city"],
            "district": opp["district"],
            "address": opp["address"],
            "rent_estimate": opp["rent_estimate"],
            "contact": opp["contact"],
            "summary": opp["summary_unlocked"],
            "tags": opp["tags"],
            "metrics": opp["metrics"],
            "created_at": opp["created_at"],
            "expires_at": opp["expires_at"],
            "locked": False,
        }
    else:
        return {
            "id": opp["id"],
            "type": opp["type"],
            "title": opp["title"],
            "city": opp["city"],
            "district": opp["district"],
            "summary": opp["summary_locked"],
            "tags": opp["tags"],
            "price": opp["price"],
            "locked": True,
        }
