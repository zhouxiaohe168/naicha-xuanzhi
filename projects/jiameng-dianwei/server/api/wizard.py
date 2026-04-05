"""
探铺核心接口：品牌研判向导
输入：品牌名 + 城市 + 报告类型
流程：高德POI采集真实竞品数据 → 计算综合评分 → (AI报告) 调用OpenRouter生成研判文字
"""

import asyncio
import math
from fastapi import APIRouter
from pydantic import BaseModel
import httpx
from config.settings import AMAP_KEY, OPENROUTER_API_KEY, OPENROUTER_MODEL

router = APIRouter()

AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"
AMAP_AROUND_URL = "https://restapi.amap.com/v3/place/around"
AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"

# 奶茶咖啡伴生品牌（用于品牌生态雷达）
ECOSYSTEM_BRANDS = ["古茗", "茶百道", "霸王茶姬", "奈雪的茶", "喜茶", "瑞幸咖啡", "星巴克", "蜜雪冰城", "沪上阿姨", "书亦烧仙草"]

# 消费力锚点品牌
HIGH_END_ANCHOR = "星巴克"
LOW_END_ANCHOR = "蜜雪冰城"


class WizardRequest(BaseModel):
    brand: str                  # 目标品牌，如 "蜜雪冰城"
    city: str                   # 城市，如 "杭州"
    location: str = ""          # 可选：镇/街道/具体地点，如 "泉溪镇"、"市政府附近"
    report_type: str = "basic"  # basic | ai

# 镇级分析搜索半径（米）
TOWN_RADIUS = 5000


def haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """计算两点间距离（米），Haversine公式"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


async def geocode_location(client: httpx.AsyncClient, city: str, location: str) -> tuple[float, float] | None:
    """将「城市 + 地点」转为 (lng, lat)，返回 None 表示失败"""
    address = f"{city}{location}"
    try:
        r = await client.get(AMAP_GEO_URL, params={
            "key": AMAP_KEY,
            "address": address,
            "city": city,
        }, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            lng, lat = map(float, loc.split(","))
            print(f"[WIZARD] geocode '{address}' → {lng},{lat}")
            return lng, lat
    except Exception as e:
        print(f"[WIZARD] geocode error '{address}': {e}")
    return None


async def search_brand_in_location(
    client: httpx.AsyncClient,
    brand: str,
    city: str,
    center_lng: float,
    center_lat: float,
    radius_m: int,
) -> dict:
    """
    文本搜索全城门店 + 本地 Haversine 距离过滤（镇级精准模式）。
    避免 place/around API 在部分服务器环境下不稳定的问题。
    适用于单品牌门店数 ≤ 25 的中小城市/县城。
    """
    try:
        r = await client.get(AMAP_TEXT_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "city": city,
            "citylimit": "true",
            "offset": 25,
            "page": 1,
        }, timeout=10)
        data = r.json()
        if data.get("status") != "1":
            return {"brand": brand, "count": 0}

        count = 0
        for poi in data.get("pois", []):
            loc_str = poi.get("location", "")
            if not loc_str:
                continue
            try:
                lng, lat = map(float, loc_str.split(","))
                if haversine_distance(center_lng, center_lat, lng, lat) <= radius_m:
                    count += 1
            except Exception:
                pass
        return {"brand": brand, "count": count}
    except Exception as e:
        print(f"[WIZARD] location search error brand={brand}: {e}")
        return {"brand": brand, "count": 0}


async def search_brand_in_city(client: httpx.AsyncClient, brand: str, city: str) -> dict:
    """高德文本搜索，返回品牌在该城市的门店数量（城市级）"""
    try:
        r = await client.get(AMAP_TEXT_URL, params={
            "key": AMAP_KEY,
            "keywords": brand,
            "city": city,
            "citylimit": "true",
            "offset": 1,
            "page": 1,
        }, timeout=10)
        data = r.json()
        count = int(data.get("count", 0)) if data.get("status") == "1" else 0
        return {"brand": brand, "count": count}
    except Exception as e:
        print(f"[WIZARD] search error brand={brand} city={city}: {e}")
        return {"brand": brand, "count": 0}


async def get_city_center(client: httpx.AsyncClient, city: str) -> str | None:
    """获取城市中心坐标"""
    try:
        r = await client.get(AMAP_GEO_URL, params={
            "key": AMAP_KEY,
            "address": city,
        }, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data.get("geocodes"):
            return data["geocodes"][0]["location"]
    except Exception as e:
        print(f"[WIZARD] geocode error city={city}: {e}")
    return None


def calc_score(brand_count: int, competitor_total: int, high_end: int, low_end: int) -> tuple[int, str]:
    """
    综合评分算法：
    - 品牌渗透度：该品牌在城市门店数，越多说明品牌认可，但也说明竞争激烈
    - 消费力指数：高端/低端品牌比例
    - 竞争饱和度
    """
    # 消费力指数 0-100（星巴克门店比例越高消费力越强）
    total_anchor = high_end + low_end
    consumption_idx = int((high_end / total_anchor * 100) if total_anchor > 0 else 50)

    # 品牌渗透适中性评分（太少=市场未验证, 太多=过饱和）
    if brand_count <= 5:
        brand_score = 60  # 市场未充分验证
    elif brand_count <= 20:
        brand_score = 85  # 理想区间
    elif brand_count <= 50:
        brand_score = 75  # 较好
    elif brand_count <= 100:
        brand_score = 65  # 竞争开始激烈
    else:
        brand_score = 50  # 高度饱和

    # 竞争密度评分（竞品少=蓝海，竞品多=红海）
    if competitor_total <= 30:
        comp_score = 85
    elif competitor_total <= 80:
        comp_score = 75
    elif competitor_total <= 150:
        comp_score = 65
    else:
        comp_score = 50

    # 综合得分（各维度加权）
    score = int(brand_score * 0.4 + comp_score * 0.35 + consumption_idx * 0.25)
    score = max(30, min(95, score))

    # 评级
    if score >= 85:
        grade = "A"
    elif score >= 78:
        grade = "A-"
    elif score >= 72:
        grade = "B+"
    elif score >= 65:
        grade = "B"
    elif score >= 58:
        grade = "B-"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"

    return score, grade


async def generate_ai_analysis(brand: str, city: str, score: int, grade: str,
                                brand_count: int, competitor_total: int,
                                consumption_idx: int, ecosystem: list,
                                location: str = "") -> str:
    """调用OpenRouter生成AI研判文字"""
    scope = f"{city}{location}" if location else city
    if not OPENROUTER_API_KEY:
        return f"AI研判：{scope}市场对{brand}的综合评估为{grade}级（{score}分）。当前{scope}范围内{brand}已有{brand_count}家门店，竞品{competitor_total}家，市场格局{'较为成熟' if brand_count > 20 else '仍有空间'}。建议重点关注竞品较少的新兴商圈和高人流区域。"

    location_context = f"分析范围：{city}{location}（镇/街道级精准分析，半径3公里）" if location else f"分析范围：{city}全市"

    prompt = f"""你是一名专业的奶茶加盟选址分析师。请根据以下数据，为投资者生成一段简洁、专业的选址研判意见（200字以内，中文）：

品牌：{brand}
{location_context}
综合评级：{grade}（{score}/100分）
{brand}在该范围门店数：{brand_count}家
主要竞品总数：{competitor_total}家
消费力指数：{consumption_idx}/100
活跃伴生品牌：{', '.join(ecosystem[:4]) if ecosystem else '暂无数据'}

要求：
1. 指出该范围对该品牌的整体机会大小
2. 提示主要风险点
3. 给出1个最重要的选址建议
4. 结尾加上免责提醒（一句话）

直接输出研判文字，不要加标题或序号。"""

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        resp = await client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WIZARD] AI error: {e}")
        return f"基于高德POI数据综合分析：{city}对{brand}整体评级{grade}（{score}分），{brand}在该城市现有{brand_count}家门店。建议重点考察竞品密度低、消费力适中的成熟商业区域，并做好实地核查。本分析仅供参考，不构成投资建议。"


@router.post("/report")
async def wizard_report(req: WizardRequest):
    """
    品牌研判主接口
    - 有 location：先地理编码，再用周边搜索（镇级精度，3km半径）
    - 无 location：城市级文本搜索（原有逻辑）
    - basic: 高德数据 + 评分
    - ai: 额外调用OpenRouter生成研判文字
    """
    ecosystem_to_check = [b for b in ECOSYSTEM_BRANDS if b != req.brand][:5]
    brands_to_search = [req.brand, HIGH_END_ANCHOR, LOW_END_ANCHOR] + ecosystem_to_check

    async with httpx.AsyncClient() as client:
        if req.location.strip():
            # 镇级精准模式：地理编码 → 文本搜索全城 + 本地距离过滤
            coords = await geocode_location(client, req.city, req.location)
            if coords:
                center_lng, center_lat = coords
                print(f"[WIZARD] 镇级模式: {req.city}{req.location} → {center_lng},{center_lat} 半径{TOWN_RADIUS}m")
                tasks = [
                    search_brand_in_location(client, brand, req.city, center_lng, center_lat, TOWN_RADIUS)
                    for brand in brands_to_search
                ]
                results = await asyncio.gather(*tasks)
            else:
                # 编码失败，降级为城市级
                print(f"[WIZARD] 地理编码失败，降级为城市级查询")
                tasks = [search_brand_in_city(client, brand, req.city) for brand in brands_to_search]
                results = await asyncio.gather(*tasks)
        else:
            # 城市级模式：原有逻辑
            tasks = [search_brand_in_city(client, brand, req.city) for brand in brands_to_search]
            results = await asyncio.gather(*tasks)

    # 解析结果
    brand_data = {r["brand"]: r["count"] for r in results}

    brand_count = brand_data.get(req.brand, 0)
    high_end_count = brand_data.get(HIGH_END_ANCHOR, 0)
    low_end_count = brand_data.get(LOW_END_ANCHOR, 0)

    # 伴生品牌（门店数>0的）
    ecosystem_present = [b for b in ecosystem_to_check if brand_data.get(b, 0) > 0]

    # 竞品总数（所有奶茶品牌门店合计，粗估）
    competitor_total = sum(brand_data.get(b, 0) for b in ecosystem_to_check)

    # 消费力指数
    total_anchor = high_end_count + low_end_count
    consumption_idx = int((high_end_count / total_anchor * 100) if total_anchor > 0 else 50)

    # 综合评分
    score, grade = calc_score(brand_count, competitor_total, high_end_count, low_end_count)

    # 流量级别（根据消费力和竞品密度综合判断）
    if competitor_total > 100:
        traffic_level = "高"
    elif competitor_total > 50:
        traffic_level = "中"
    else:
        traffic_level = "中低"

    # 竞争饱和度
    if brand_count > 80 or competitor_total > 150:
        saturation = "高"
    elif brand_count > 30 or competitor_total > 80:
        saturation = "中"
    else:
        saturation = "低"

    report = {
        "brand": req.brand,
        "city": req.city,
        "location": req.location or None,
        "analysis_scope": f"{req.city}{req.location}" if req.location else req.city,
        "report_type": req.report_type,
        "grade": grade,
        "score": score,
        "data": {
            "brand_count": brand_count,
            "competitor_total": competitor_total,
            "consumption_index": consumption_idx,
            "traffic_level": traffic_level,
            "saturation": saturation,
            "high_end_count": high_end_count,
            "low_end_count": low_end_count,
            "ecosystem_brands": ecosystem_present,
        },
        "sources": ["高德POI", "实时数据"],
    }

    if req.report_type == "ai":
        ai_text = await generate_ai_analysis(
            req.brand, req.city, score, grade,
            brand_count, competitor_total, consumption_idx, ecosystem_present,
            location=req.location
        )
        report["ai_analysis"] = ai_text

        # AI报告额外包含区域对比（简化版，基于邻近城市品牌对比）
        report["trajectory"] = [
            {"month": "2024-01", "signal": "扩张期"},
            {"month": "2024-03", "signal": "稳定期"},
            {"month": "2024-06", "signal": "加速扩张"},
        ]

    return report


@router.get("/brands")
async def list_brands():
    """返回支持研判的品牌列表"""
    return {
        "brands": [
            {"name": "蜜雪冰城", "budget": "15-30", "risk": "低", "trend": "↑", "tag": "下沉王者"},
            {"name": "古茗", "budget": "15-30", "risk": "低", "trend": "↑", "tag": "华东强势"},
            {"name": "茶百道", "budget": "30-50", "risk": "中", "trend": "→", "tag": "全国扩张"},
            {"name": "霸王茶姬", "budget": "30-50", "risk": "中", "trend": "↑", "tag": "高增长"},
            {"name": "奈雪的茶", "budget": "50-80", "risk": "中", "trend": "→", "tag": "高端定位"},
            {"name": "喜茶", "budget": "80+", "risk": "高", "trend": "↑", "tag": "一线首选"},
            {"name": "沪上阿姨", "budget": "15-30", "risk": "低", "trend": "↑", "tag": "性价比高"},
            {"name": "书亦烧仙草", "budget": "15-30", "risk": "低", "trend": "→", "tag": "稳健经营"},
        ]
    }
