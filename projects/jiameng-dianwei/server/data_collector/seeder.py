"""
金华市商圈种子数据
功能：初始化金华市核心商圈（手动维护），首次运行时写入数据库
"""

from sqlalchemy.orm import Session
from models.schemas import BusinessDistrict

# 金华市核心商圈（名称 + 中心坐标）
# 坐标来源：高德地图，格式为 (纬度, 经度)
JINHUA_DISTRICTS = [
    {"name": "万达广场商圈",     "latitude": 29.0847, "longitude": 119.6522},
    {"name": "义乌国际商贸城",   "latitude": 29.3063, "longitude": 120.0755},
    {"name": "金华步行街",       "latitude": 29.1038, "longitude": 119.6482},
    {"name": "宾虹路商业区",     "latitude": 29.0912, "longitude": 119.6489},
    {"name": "义乌商城大道",     "latitude": 29.3124, "longitude": 120.0812},
    {"name": "金华火车站商圈",   "latitude": 29.1010, "longitude": 119.6527},
    {"name": "金东区多湖商圈",   "latitude": 29.0769, "longitude": 119.6978},
    {"name": "浦江县城商圈",     "latitude": 29.4523, "longitude": 119.8921},
    {"name": "兰溪市区商圈",     "latitude": 29.2082, "longitude": 119.4621},
    {"name": "东阳市商圈",       "latitude": 29.2731, "longitude": 120.2413},
]


def seed_districts(db: Session):
    """
    初始化商圈数据，已存在则跳过
    """
    existing = db.query(BusinessDistrict).filter(
        BusinessDistrict.city == "金华市"
    ).count()

    if existing > 0:
        print(f"[初始化] 商圈数据已存在（{existing}条），跳过")
        return

    for d in JINHUA_DISTRICTS:
        db.add(BusinessDistrict(
            city="金华市",
            name=d["name"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            foot_traffic_level="medium",  # 采集后会自动更新
        ))

    db.commit()
    print(f"[初始化] 金华市 {len(JINHUA_DISTRICTS)} 个商圈写入完成")
