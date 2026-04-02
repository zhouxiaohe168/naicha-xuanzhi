"""
实时选址分析接口
逻辑：找出参照品牌门店位置 → 检查每个位置周边有没有目标品牌 → 没有的就是机会点
"""
import asyncio
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from config.settings import AMAP_KEY

router = APIRouter()

AMAP_GEO_URL    = "https://restapi.amap.com/v3/geocode/geo"
AMAP_AROUND_URL = "https://restapi.amap.com/v3/place/around"
AMAP_TEXT_URL   = "https://restapi.amap.com/v3/place/text"


class AnalyzeRequest(BaseModel):
    brand:    str
    anchors:  List[str]
    city:     str
    district: str
    street:   str
    radius:   int = 1000   # 判断"附近有没有目标品牌"的范围，单位米


# ── 高德 API 基础调用 ──────────────────────────────────────

async def geocode(client: httpx.AsyncClient, address: str, city: str) -> Optional[str]:
    """地址 → 'lng,lat' 字符串，失败返回 None"""
    try:
        r = await client.get(AMAP_GEO_URL, params={
            "key": AMAP_KEY, "address": address, "city": city,
        }, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data.get("geocodes"):
            return data["geocodes"][0]["location"]
    except Exception as e:
        print(f"[GEOCODE ERROR] {e}", flush=True)
    return None


async def get_stores_near(client: httpx.AsyncClient, brand: str, location: str,
                          radius: int = 2000, max_count: int = 20) -> tuple[int, list]:
    """
    在 location 周边 radius 米内找 brand 的门店。
    返回 (总数, [{"name","address","location"}, ...])
    最多返回 max_count 条（用于机会点检测）
    """
    try:
        r = await client.get(AMAP_AROUND_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "location": location,
            "radius": radius,
            "offset": 25,
            "page": 1,
            "extensions": "base",
        }, timeout=15)
        data = r.json()
        print(f"[STORES] brand={brand} loc={location} radius={radius} "
              f"status={data.get('status')} count={data.get('count')}", flush=True)
        if data.get("status") != "1":
            return 0, []
        total = int(data.get("count", 0))
        pois  = data.get("pois", []) or []
        stores = [
            {
                "name":     p.get("name", ""),
                "address":  p.get("address", "") or "",
                "location": p.get("location", ""),
            }
            for p in pois[:max_count]
            if p.get("location")
        ]
        return total, stores
    except Exception as e:
        print(f"[STORES ERROR] brand={brand} error={e}", flush=True)
        return 0, []


async def count_near(client: httpx.AsyncClient, brand: str,
                     location: str, radius: int) -> int:
    """检查 location 周边 radius 米内 brand 有多少家"""
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
        if data.get("status") == "1":
            return int(data.get("count", 0))
    except Exception as e:
        print(f"[COUNT ERROR] brand={brand} error={e}", flush=True)
    return 0


async def nearest_distance(client: httpx.AsyncClient, brand: str,
                            location: str, search_radius: int = 5000) -> Optional[int]:
    """
    找 location 周边 search_radius 米内最近的 brand 门店，返回距离（米）。
    找不到返回 None（表示超过 search_radius）
    """
    try:
        r = await client.get(AMAP_AROUND_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "location": location,
            "radius": search_radius,
            "offset": 1,
            "page": 1,
            "extensions": "base",
        }, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data.get("pois"):
            d = data["pois"][0].get("distance")
            return int(d) if d else None
    except Exception as e:
        print(f"[DISTANCE ERROR] brand={brand} error={e}", flush=True)
    return None


# ── 主接口 ──────────────────────────────────────────────

@router.post("/")
async def analyze(req: AnalyzeRequest):
    """
    查询流程：
    1. 地理编码街道中心点
    2. 在中心点 2km 内找所有参照品牌门店（含坐标）
    3. 对每个参照门店：检查目标品牌在 req.radius 米内数量
    4. 数量为 0 的就是"机会点"
    5. 对每个机会点：找最近目标品牌距离
    """
    async with httpx.AsyncClient() as client:

        # 1. 地理编码
        center = await geocode(client, req.street, req.city)
        if not center:
            return {
                "error": "无法定位该街道，请检查城市和街道名称是否正确",
                "location": {"city": req.city, "street": req.street},
            }

        # 2. 并发获取各参照品牌门店列表 + 目标品牌总数
        anchor_store_tasks = [
            get_stores_near(client, brand, center, radius=2000, max_count=20)
            for brand in req.anchors
        ]
        target_total_task = count_near(client, req.brand, center, radius=2000)

        results = await asyncio.gather(*anchor_store_tasks, target_total_task)
        anchor_raw = results[:-1]          # [(total, stores), ...]
        target_total = results[-1]

        anchor_results = [
            {"brand": brand, "count": total, "stores": stores}
            for brand, (total, stores) in zip(req.anchors, anchor_raw)
        ]

        # 3. 对每个参照门店并发检查目标品牌是否在 req.radius 内
        flat_stores = [
            (brand_info["brand"], store)
            for brand_info in anchor_results
            for store in brand_info["stores"]
        ]

        if flat_stores:
            check_tasks = [
                count_near(client, req.brand, store["location"], req.radius)
                for _, store in flat_stores
            ]
            nearby_counts = await asyncio.gather(*check_tasks)
        else:
            nearby_counts = []

        # 4. 筛出机会点
        opportunity_raw = [
            (brand, store)
            for (brand, store), cnt in zip(flat_stores, nearby_counts)
            if cnt == 0
        ]

        # 5. 对每个机会点找最近竞品距离（并发）
        if opportunity_raw:
            dist_tasks = [
                nearest_distance(client, req.brand, store["location"], search_radius=5000)
                for _, store in opportunity_raw
            ]
            distances = await asyncio.gather(*dist_tasks)
        else:
            distances = []

    # ── 整理返回 ──────────────────────────────────────────

    # 参照品牌汇总（只返回数量，不含 stores 列表，节省流量）
    anchor_summary = [
        {"brand": r["brand"], "count": r["count"]}
        for r in anchor_results
    ]

    def fmt_dist(d_meters):
        if d_meters is None:
            return "5km+"
        if d_meters < 1000:
            return f"{d_meters}m"
        return f"{d_meters / 1000:.1f}km"

    opportunity_spots = [
        {
            "anchor_brand":   brand,
            "anchor_name":    store["name"],
            "anchor_address": store["address"],
            "location":       store["location"],
            "nearest_target": fmt_dist(dist),      # 最近目标品牌距离，如 "2.3km"
            "nearest_m":      dist,                 # 原始米数，前端可用
        }
        for (brand, store), dist in zip(opportunity_raw, distances)
    ]

    # 按最近竞品距离降序（越远越好）
    opportunity_spots.sort(key=lambda x: x["nearest_m"] or 0, reverse=True)

    total_anchors = sum(r["count"] for r in anchor_summary)

    return {
        "location": {
            "city":     req.city,
            "district": req.district,
            "street":   req.street,
            "center":   center,
        },
        "brand":             req.brand,
        "anchor_results":    anchor_summary,
        "target_total":      target_total,
        "opportunity_count": len(opportunity_spots),
        "opportunity_spots": opportunity_spots,   # 前端免费层隐藏地址，付费后显示
        "summary": {
            "total_anchors":     total_anchors,
            "target_count":      target_total,
            "opportunity_count": len(opportunity_spots),
        },
    }
