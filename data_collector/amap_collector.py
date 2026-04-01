"""
高德地图 POI 数据采集器
功能：搜索指定商圈周边500米的奶茶/咖啡门店
"""

import httpx
import asyncio
from typing import List, Dict
from config.settings import AMAP_KEY

# 高德API地址
AMAP_SEARCH_URL = "https://restapi.amap.com/v3/place/around"

# 奶茶/咖啡品牌关键词映射（用于识别品牌）
TEA_BRANDS = [
    "蜜雪冰城", "喜茶", "奈雪", "茶百道", "古茗", "沪上阿姨",
    "书亦烧仙草", "甜啦啦", "益禾堂", "霸王茶姬", "茉酸奶", "一点点",
    "CoCo", "都可", "快乐柠檬", "柠季", "茶颜悦色", "七分甜",
]
COFFEE_BRANDS = [
    "瑞幸", "库迪", "星巴克", "麦咖啡", "幸运咖", "Manner",
    "Tim Hortons", "皮爷", "Costa", "挪瓦咖啡",
]

# 高德POI分类代码
# 050500=茶艺/茶室, 050600=咖啡厅
TEA_TYPE_CODE = "050500|050501|050502"
COFFEE_TYPE_CODE = "050600|050601"


def identify_brand(shop_name: str, category: str) -> str:
    """从店名识别品牌"""
    brand_list = TEA_BRANDS if category == "tea" else COFFEE_BRANDS
    for brand in brand_list:
        if brand in shop_name:
            return brand
    return "其他"


async def fetch_pois(latitude: float, longitude: float, type_code: str, radius: int = 500) -> List[Dict]:
    """
    调用高德API搜索周边POI
    :param latitude: 纬度
    :param longitude: 经度
    :param type_code: 高德分类代码
    :param radius: 搜索半径（米），默认500米
    :return: POI列表
    """
    all_pois = []
    page = 1

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            params = {
                "key": AMAP_KEY,
                "location": f"{longitude},{latitude}",  # 高德是经度在前
                "types": type_code,
                "radius": radius,
                "offset": 25,   # 每页25条（高德最大值）
                "page": page,
                "extensions": "base",
            }

            try:
                response = await client.get(AMAP_SEARCH_URL, params=params)
                data = response.json()
            except Exception as e:
                print(f"[采集错误] 高德API请求失败: {e}")
                break

            if data.get("status") != "1":
                print(f"[采集错误] 高德API返回错误: {data.get('info')}")
                break

            pois = data.get("pois", [])
            if not pois:
                break

            all_pois.extend(pois)

            # 超过100条或无更多数据则停止
            if len(pois) < 25 or len(all_pois) >= 100:
                break

            page += 1
            await asyncio.sleep(0.2)  # 避免请求过快

    return all_pois


async def collect_district_shops(district_id: int, latitude: float, longitude: float) -> Dict:
    """
    采集某商圈的全部奶茶/咖啡门店数据
    :return: {"tea_shops": [...], "coffee_shops": [...]}
    """
    print(f"[采集] 开始采集商圈 {district_id}，坐标({latitude}, {longitude})")

    # 并发搜索奶茶和咖啡
    tea_pois, coffee_pois = await asyncio.gather(
        fetch_pois(latitude, longitude, TEA_TYPE_CODE),
        fetch_pois(latitude, longitude, COFFEE_TYPE_CODE),
    )

    def parse_shops(pois: List[Dict], category: str) -> List[Dict]:
        shops = []
        for poi in pois:
            location = poi.get("location", "0,0").split(",")
            name = poi.get("name", "")
            shops.append({
                "district_id": district_id,
                "name": name,
                "brand": identify_brand(name, category),
                "category": category,
                "longitude": float(location[0]) if len(location) == 2 else longitude,
                "latitude": float(location[1]) if len(location) == 2 else latitude,
                "address": poi.get("address", ""),
                "rating": float(poi.get("biz_ext", {}).get("rating", 0) or 0),
            })
        return shops

    tea_shops = parse_shops(tea_pois, "tea")
    coffee_shops = parse_shops(coffee_pois, "coffee")

    print(f"[采集] 商圈 {district_id} 完成：奶茶{len(tea_shops)}家，咖啡{len(coffee_shops)}家")
    return {"tea_shops": tea_shops, "coffee_shops": coffee_shops}
