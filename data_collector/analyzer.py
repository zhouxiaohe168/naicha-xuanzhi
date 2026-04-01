"""
商圈分析引擎
功能：根据采集到的门店数据，计算商圈分析指标并写入数据库
"""

from collections import Counter
from sqlalchemy.orm import Session
from models.schemas import Shop, DistrictAnalysis, BusinessDistrict
from data_collector.amap_collector import collect_district_shops


def calc_foot_traffic(tea_count: int, coffee_count: int) -> str:
    """根据门店密度估算人流量等级"""
    total = tea_count + coffee_count
    if total >= 15:
        return "high"
    elif total >= 6:
        return "medium"
    else:
        return "low"


def calc_competition_saturation(tea_count: int, coffee_count: int) -> str:
    """计算竞争饱和度"""
    total = tea_count + coffee_count
    if total >= 20:
        return "high"
    elif total >= 10:
        return "medium"
    else:
        return "low"


def calc_consumption_heat(tea_count: int, coffee_count: int) -> str:
    """计算消费热度（简单版：用门店数量代理）"""
    total = tea_count + coffee_count
    if total >= 12:
        return "high"
    elif total >= 5:
        return "medium"
    else:
        return "low"


async def update_district(district: BusinessDistrict, db: Session):
    """
    对单个商圈执行完整的数据采集+分析+写库
    """
    # 1. 采集门店数据
    result = await collect_district_shops(district.id, district.latitude, district.longitude)
    tea_shops = result["tea_shops"]
    coffee_shops = result["coffee_shops"]
    all_shops = tea_shops + coffee_shops

    # 2. 删除旧门店数据，写入新数据
    db.query(Shop).filter(Shop.district_id == district.id).delete()
    for shop_data in all_shops:
        db.add(Shop(**shop_data))

    # 3. 计算品牌分布
    brand_counter = Counter(s["brand"] for s in all_shops if s["brand"] != "其他")
    brand_distribution = dict(brand_counter.most_common(20))

    tea_count = len(tea_shops)
    coffee_count = len(coffee_shops)

    # 4. 更新商圈人流量等级
    district.foot_traffic_level = calc_foot_traffic(tea_count, coffee_count)

    # 5. 写入/更新商圈分析表
    analysis = db.query(DistrictAnalysis).filter(
        DistrictAnalysis.district_id == district.id
    ).first()

    if analysis:
        analysis.tea_shop_count = tea_count
        analysis.coffee_shop_count = coffee_count
        analysis.brand_distribution = brand_distribution
        analysis.competition_saturation = calc_competition_saturation(tea_count, coffee_count)
        analysis.consumption_heat = calc_consumption_heat(tea_count, coffee_count)
    else:
        db.add(DistrictAnalysis(
            district_id=district.id,
            tea_shop_count=tea_count,
            coffee_shop_count=coffee_count,
            brand_distribution=brand_distribution,
            surrounding_facilities={},  # 后续可扩展：学校/写字楼/小区
            competition_saturation=calc_competition_saturation(tea_count, coffee_count),
            consumption_heat=calc_consumption_heat(tea_count, coffee_count),
        ))

    db.commit()
    print(f"[分析] 商圈「{district.name}」更新完成")


async def run_full_collection(db: Session):
    """
    全量采集：对所有商圈执行数据更新
    每周定时调用此函数
    """
    districts = db.query(BusinessDistrict).all()
    print(f"[全量采集] 开始，共 {len(districts)} 个商圈")

    for district in districts:
        try:
            await update_district(district, db)
        except Exception as e:
            print(f"[全量采集] 商圈「{district.name}」失败: {e}")

    print("[全量采集] 完成")
