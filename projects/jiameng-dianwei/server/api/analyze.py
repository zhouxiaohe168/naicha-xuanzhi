"""
实时选址分析接口
调用高德地图 API，统计锚点品牌和目标品牌在指定街道周边的门店数量
"""
import asyncio
import httpx
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from config.settings import AMAP_KEY

logger = logging.getLogger(__name__)

router = APIRouter()

AMAP_GEO_URL    = "https://restapi.amap.com/v3/geocode/geo"
AMAP_AROUND_URL = "https://restapi.amap.com/v3/place/around"
AMAP_TEXT_URL   = "https://restapi.amap.com/v3/place/text"


class AnalyzeRequest(BaseModel):
    brand:   str
    anchors: List[str]
    city:    str
    district: str
    street:  str
    radius:  int = 1000


async def geocode(client: httpx.AsyncClient, address: str, city: str) -> tuple[float, float] | None:
    """将地址转成经纬度"""
    try:
        r = await client.get(AMAP_GEO_URL, params={
            "key": AMAP_KEY,
            "address": address,
            "city": city,
        }, timeout=10)
        data = r.json()
        print(f"[GEOCODE] address={address} city={city} status={data.get('status')} info={data.get('info')} count={data.get('count')}", flush=True)
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            lng, lat = loc.split(",")
            return float(lng), float(lat)
    except Exception as e:
        print(f"[GEOCODE ERROR] address={address} error={e}", flush=True)
    return None


async def count_brand(client: httpx.AsyncClient, brand: str, location: str, radius: int, city: str) -> int:
    """查询某品牌在 location 周边 radius 米内的门店数"""
    try:
        r = await client.get(AMAP_AROUND_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "location": location,
            "radius": radius,
            "offset": 1,
            "page": 1,
            "extensions": "base",
        }, timeout=10)
        data = r.json()
        print(f"[AROUND] brand={brand} status={data.get('status')} info={data.get('info')} count={data.get('count')}", flush=True)
        if data.get("status") == "1":
            return int(data.get("count", 0))
    except Exception as e:
        print(f"[AROUND ERROR] brand={brand} error={e}", flush=True)
    return 0


async def count_brand_text(client: httpx.AsyncClient, brand: str, city: str, district: str) -> int:
    """文本搜索（兜底）"""
    try:
        r = await client.get(AMAP_TEXT_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "city": city,
            "district": district,
            "citylimit": "true",
            "offset": 1,
            "page": 1,
        }, timeout=10)
        data = r.json()
        print(f"[TEXT] brand={brand} city={city} status={data.get('status')} info={data.get('info')} count={data.get('count')}", flush=True)
        if data.get("status") == "1":
            return int(data.get("count", 0))
    except Exception as e:
        print(f"[TEXT ERROR] brand={brand} error={e}", flush=True)
    return 0


@router.post("/")
async def analyze(req: AnalyzeRequest):
    """
    查询锚点品牌 + 目标品牌在指定街道行政区域内的门店总数
    使用文本搜索覆盖整个街道，而非半径圆圈
    """
    async with httpx.AsyncClient() as client:
        # 1. 并发文本搜索：按街道行政区域统计（数据最完整）
        all_brands = req.anchors + [req.brand]
        tasks = [
            count_brand_text(client, brand, req.city, req.street)
            for brand in all_brands
        ]
        counts = await asyncio.gather(*tasks)

        # 2. 地理编码：仅用于前端地图定位展示
        coord = await geocode(client, req.street, req.city)

    # 3. 整理结果
    anchor_results = [
        {"brand": brand, "count": cnt}
        for brand, cnt in zip(req.anchors, counts[:len(req.anchors)])
    ]
    target_count = counts[len(req.anchors)] if len(counts) > len(req.anchors) else 0

    total_anchors = sum(r["count"] for r in anchor_results)

    # 空白机会评分（0-10）：锚点多说明客流旺，目标品牌少说明空白大
    anchor_avg = total_anchors / max(len(req.anchors), 1)
    if anchor_avg == 0:
        anchor_score = 0.0
    elif anchor_avg <= 3:
        anchor_score = 3.0
    elif anchor_avg <= 8:
        anchor_score = 5.0
    elif anchor_avg <= 15:
        anchor_score = 7.0
    else:
        anchor_score = 9.0

    if target_count == 0:
        gap_bonus = 1.0
    elif target_count <= 2:
        gap_bonus = 0.5
    elif target_count <= 5:
        gap_bonus = 0.0
    else:
        gap_bonus = -1.0

    gap_score = round(min(max(anchor_score + gap_bonus, 0), 10), 1)

    return {
        "location": {
            "city": req.city,
            "district": req.district,
            "street": req.street,
            "geocoded": coord is not None,
        },
        "brand": req.brand,
        "anchor_results": anchor_results,
        "target_result": {
            "brand": req.brand,
            "count": target_count,
        },
        "summary": {
            "total_anchors": total_anchors,
            "target_count": target_count,
            "gap_score": gap_score,
        },
    }
