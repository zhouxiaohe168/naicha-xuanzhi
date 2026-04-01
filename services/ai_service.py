"""
Claude AI 研判服务
功能：根据商圈数据调用 Claude API 生成选址研判报告
"""

import json
import re
import anthropic
from pathlib import Path
from config.settings import ANTHROPIC_API_KEY

# 读取 prompt 模板
_PROMPT_PATH = Path(__file__).parent.parent / "ai_prompts" / "ai_judge.md"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

TRAFFIC_CN = {"high": "高", "medium": "中", "low": "低"}
HEAT_CN = {"high": "高", "medium": "中", "low": "低"}


def _build_prompt(district: dict, analysis: dict, shops: list) -> str:
    """将商圈数据填入 prompt 模板"""
    brands = list(analysis.get("brand_distribution", {}).keys())
    surrounding = analysis.get("surrounding_facilities", {})

    surrounding_desc = "、".join(
        f"{v}个{k}" for k, v in surrounding.items() if v
    ) or "暂无数据"

    return _PROMPT_TEMPLATE.format(
        district_name=district["name"],
        city=district["city"],
        tea_count=analysis.get("tea_shop_count", 0),
        coffee_count=analysis.get("coffee_shop_count", 0),
        brands="、".join(brands) if brands else "暂无数据",
        traffic_level=TRAFFIC_CN.get(district.get("foot_traffic_level", "medium"), "中"),
        surrounding=surrounding_desc,
    )


def _parse_response(content: str) -> dict:
    """从 Claude 回复中提取 JSON"""
    # 优先提取 ```json ... ``` 块
    match = re.search(r"```json\s*([\s\S]+?)\s*```", content)
    if match:
        return json.loads(match.group(1))
    # 兜底：整段当作 JSON
    return json.loads(content)


async def generate_ai_report(district: dict, analysis: dict, shops: list) -> dict:
    """
    调用 Claude API 生成 AI 研判报告
    :return: 结构化报告字典
    :raises: RuntimeError（API未配置 或 解析失败）
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY 未配置，请在 .env 中填入 Claude API Key")

    prompt = _build_prompt(district, analysis, shops)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    try:
        return _parse_response(raw)
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"AI 返回格式解析失败: {e}\n原始内容: {raw[:300]}")
