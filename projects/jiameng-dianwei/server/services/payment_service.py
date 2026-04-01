"""
支付服务
- mock：开发测试用，立即支付成功
- wechat：微信支付（需填入商户号和密钥）
- alipay：支付宝（需填入 app_id 和私钥）
"""

import hashlib
import time
import uuid
from config.settings import (
    WECHAT_MCH_ID, WECHAT_API_KEY,
    ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY,
)


# ──────────────────────────────────────────────
# Mock 支付（测试用）
# ──────────────────────────────────────────────

def create_mock_payment(order_id: int, amount: float) -> dict:
    return {
        "payment_method": "mock",
        "status": "paid",
        "order_id": order_id,
    }


# ──────────────────────────────────────────────
# 微信支付（JSAPI / H5）
# ──────────────────────────────────────────────

def _wechat_sign(params: dict, api_key: str) -> str:
    """微信支付签名算法"""
    sorted_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v)
    sign_str = f"{sorted_str}&key={api_key}"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def create_wechat_payment(order_id: int, amount: float, openid: str = "") -> dict:
    """
    创建微信支付订单
    需要配置：WECHAT_MCH_ID, WECHAT_API_KEY
    文档：https://pay.weixin.qq.com/wiki/doc/api/jsapi.php?chapter=9_1
    """
    if not WECHAT_MCH_ID or not WECHAT_API_KEY:
        raise RuntimeError("微信支付未配置，请在 .env 填入 WECHAT_MCH_ID 和 WECHAT_API_KEY")

    params = {
        "appid": "wx_your_appid",          # TODO: 填入小程序/公众号 AppID
        "mch_id": WECHAT_MCH_ID,
        "nonce_str": uuid.uuid4().hex,
        "body": "奶茶选址通-商圈报告",
        "out_trade_no": f"NCX{order_id}{int(time.time())}",
        "total_fee": int(amount * 100),     # 微信支付单位是分
        "spbill_create_ip": "127.0.0.1",
        "notify_url": "https://your-domain.com/api/payment/wechat/callback",  # TODO: 替换域名
        "trade_type": "JSAPI" if openid else "H5",
        "openid": openid,
    }
    params["sign"] = _wechat_sign(params, WECHAT_API_KEY)

    # TODO: 发送请求到 https://api.mch.weixin.qq.com/pay/unifiedorder
    # 返回 prepay_id，前端用来拉起支付
    return {
        "payment_method": "wechat",
        "status": "pending",
        "order_id": order_id,
        "params": params,           # 前端用这个拉起微信支付
    }


def verify_wechat_callback(data: dict) -> bool:
    """验证微信支付回调签名"""
    if not WECHAT_API_KEY:
        return False
    sign = data.pop("sign", "")
    expected = _wechat_sign(data, WECHAT_API_KEY)
    return sign == expected


# ──────────────────────────────────────────────
# 支付宝（电脑网站支付 / 手机网站支付）
# ──────────────────────────────────────────────

def create_alipay_payment(order_id: int, amount: float, return_url: str = "") -> dict:
    """
    创建支付宝支付订单
    需要配置：ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY
    文档：https://opendocs.alipay.com/open/270/105898
    推荐使用 alipay-sdk-python 库（当前用 httpx 手动实现）
    """
    if not ALIPAY_APP_ID or not ALIPAY_PRIVATE_KEY:
        raise RuntimeError("支付宝未配置，请在 .env 填入 ALIPAY_APP_ID 和 ALIPAY_PRIVATE_KEY")

    # TODO: 使用 alipay-sdk-python 简化接入
    # pip install alipay-sdk-python
    # from alipay import AliPay
    # alipay = AliPay(appid=ALIPAY_APP_ID, app_private_key=ALIPAY_PRIVATE_KEY, ...)
    # order_string = alipay.api_alipay_trade_wap_pay(...)

    return {
        "payment_method": "alipay",
        "status": "pending",
        "order_id": order_id,
        "payment_url": "",   # TODO: alipay.api_alipay_trade_wap_pay 返回的支付 URL
    }


def verify_alipay_callback(data: dict) -> bool:
    """验证支付宝异步通知签名（生产必须验证）"""
    # TODO: 使用 alipay-sdk-python 的 verify 方法
    return True
