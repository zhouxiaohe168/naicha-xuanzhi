"""
实时选址分析接口
调用高德地图 API，统计锚点品牌和目标品牌在指定街道周边的门店数量
"""
import asyncio
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from config.settings import AMAP_KEY

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
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            lng, lat = loc.split(",")
            return float(lng), float(lat)
    except Exception:
        pass
    return None


async def count_brand(client: httpx.AsyncClient, brand: str, location: str, radius: int, city: str) -> int:
    """查询某品牌在 location 周边 radius 米内的门店数"""
    # 先尝试周边搜索（精确）
    try:
        r = await client.get(AMAP_AROUND_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "location": location,
            "radius": radius,
            "offset": 1,      # 只需 count，取1条省流量
            "page": 1,
            "extensions": "base",
        }, timeout=10)
        data = r.json()
        if data.get("status") == "1":
            return int(data.get("count", 0))
    except Exception:
        pass
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
        if data.get("status") == "1":
            return int(data.get("count", 0))
    except Exception:
        pass
    return 0


@router.post("/")
async def analyze(req: AnalyzeRequest):
    """
    查询锚点品牌 + 目标品牌在街道周边的密度
    """
    async with httpx.AsyncClient() as client:
        # 1. 地理编码：街道 + 城市
        address = f"{req.street}"
        coord = await geocode(client, address, req.city)

        if coord:
            lng, lat = coord
            location = f"{lng},{lat}"

            # 2. 并发查询所有品牌
            all_brands = req.anchors + [req.brand]
            tasks = [
                count_brand(client, brand, location, req.radius, req.city)
                for brand in all_brands
            ]
            counts = await asyncio.gather(*tasks)
        else:
            # geocode 失败 → 改用文本搜索（只能按城市+区）
            all_brands = req.anchors + [req.brand]
            tasks = [
                count_brand_text(client, brand, req.city, req.district)
                for brand in all_brands
            ]
            counts = await asyncio.gather(*tasks)

    # 3. 整理结果
    anchor_results = [
        {"brand": brand, "count": cnt}
        for brand, cnt in zip(req.anchors, counts[:len(req.anchors)])
    ]
    target_count = counts[len(req.anchors)] if len(counts) > len(req.anchors) else 0

    total_anchors = sum(r["count"] for r in anchor_results)
    # 空白分：锚点总数高、目标少 → 分数高
    anchor_score = min(total_anchors / max(len(req.anchors), 1) * 2, 10)  # 均值*2，max 10
    gap_bonus    = 3 if target_count == 0 else max(0, 3 - target_count)
    gap_score    = round(min(anchor_score + gap_bonus, 10), 1)

    return {
        "location": {
            "city": req.city,
            "district": req.district,
            "street": req.street,
            "radius": req.radius,
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
