import os
from dotenv import load_dotenv

load_dotenv()

# 项目信息
PROJECT_NAME = "探铺"
VERSION = "2.0.0"

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/naicha_xuanzhi")

# JWT认证
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 高德地图API
AMAP_KEY = os.getenv("AMAP_KEY", "")

# OpenRouter API（AI研判用）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")

# 短信服务（阿里云）
SMS_ACCESS_KEY_ID = os.getenv("SMS_ACCESS_KEY_ID", "")
SMS_ACCESS_KEY_SECRET = os.getenv("SMS_ACCESS_KEY_SECRET", "")
SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME", "探铺")
SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE", "")

# 支付宝（H5支付）
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
ALIPAY_PRIVATE_KEY = os.getenv("ALIPAY_PRIVATE_KEY", "")
ALIPAY_PUBLIC_KEY = os.getenv("ALIPAY_PUBLIC_KEY", "")
ALIPAY_NOTIFY_URL = os.getenv("ALIPAY_NOTIFY_URL", "https://your-backend.railway.app/api/payment/alipay/notify")
ALIPAY_RETURN_URL = os.getenv("ALIPAY_RETURN_URL", "https://your-frontend.vercel.app/report")

# 探铺定价（分为单位，对应人民币元×100）
PRICE_BASIC = 5900       # ¥59 位置信息包
PRICE_AI = 29900         # ¥299 AI深度报告
PRICE_OPPORTUNITY = 59900  # ¥599 机会解锁

# 前端域名（用于支付回调跳转）
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://your-frontend.vercel.app")
