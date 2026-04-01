import os
from dotenv import load_dotenv

load_dotenv()

# 项目信息
PROJECT_NAME = "奶茶选址通"
VERSION = "1.0.0"

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/naicha_xuanzhi")

# JWT认证
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 高德地图API
AMAP_KEY = os.getenv("AMAP_KEY", "")

# Claude API（AI研判用）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 短信服务（阿里云）
SMS_ACCESS_KEY_ID = os.getenv("SMS_ACCESS_KEY_ID", "")
SMS_ACCESS_KEY_SECRET = os.getenv("SMS_ACCESS_KEY_SECRET", "")
SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME", "奶茶选址通")
SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE", "")

# 微信支付
WECHAT_MCH_ID = os.getenv("WECHAT_MCH_ID", "")
WECHAT_API_KEY = os.getenv("WECHAT_API_KEY", "")

# 支付宝
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")

# 定价
PRICE_BASIC = 9.9
PRICE_AI = 59.9

# MVP城市
MVP_CITY = "金华市"
