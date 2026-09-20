from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-server")


WEATHER_DATA = {
    "北京": {
        "weather": "晴",
        "temperature": "28°C",
        "wind": "东北风 2 级",
        "suggestion": "适合外出，但中午注意防晒。",
    },
    "上海": {
        "weather": "多云",
        "temperature": "26°C",
        "wind": "东南风 3 级",
        "suggestion": "体感舒适，适合通勤和散步。",
    },
    "杭州": {
        "weather": "小雨",
        "temperature": "24°C",
        "wind": "西南风 2 级",
        "suggestion": "建议带伞，路面湿滑注意安全。",
    },
    "深圳": {
        "weather": "雷阵雨",
        "temperature": "30°C",
        "wind": "南风 3 级",
        "suggestion": "注意短时强降雨，尽量避开户外长时间停留。",
    },
    "成都": {
        "weather": "阴",
        "temperature": "21°C",
        "wind": "微风",
        "suggestion": "天气凉爽，适合外出散步。",
    },
}


@mcp.tool()
def query_weather(city: str) -> str:
    """
    查询指定城市的天气。
    """
    city = city.strip()
    data = WEATHER_DATA.get(city)

    if data is None:
        available_cities = "、".join(WEATHER_DATA)
        return f"暂时没有 {city} 的天气数据。当前支持的城市：{available_cities}。"

    return (
        f"{city}天气：{data['weather']}，"
        f"气温：{data['temperature']}，"
        f"风力：{data['wind']}。"
        f"建议：{data['suggestion']}"
    )


@mcp.tool()
def list_supported_cities() -> str:
    """列出当前天气 MCP Server 支持查询的城市。"""
    return "当前支持查询的城市：" + "、".join(WEATHER_DATA)


@mcp.tool()
def get_clothing_advice(city: str) -> str:
    """
    根据指定城市的当前天气给出穿衣建议（练习二新增工具）。

    这个工具演示了 MCP 工具之间可以共享同一份业务数据：
    它不维护独立的建议表，而是基于 query_weather 的数据推导。
    """
    city = city.strip()
    data = WEATHER_DATA.get(city)

    if data is None:
        available_cities = "、".join(WEATHER_DATA)
        return f"暂时没有 {city} 的天气数据，无法给出穿衣建议。当前支持的城市：{available_cities}。"

    temperature = int("".join(ch for ch in data["temperature"] if ch.isdigit()))
    weather = data["weather"]
    tips: list[str] = []

    if temperature >= 28:
        tips.append("天气炎热，建议穿短袖、短裤等轻薄透气的衣物")
    elif temperature >= 22:
        tips.append("气温舒适，短袖或薄长袖都可以")
    elif temperature >= 15:
        tips.append("天气偏凉，建议长袖加薄外套")
    else:
        tips.append("天气较冷，建议厚外套")

    if any(word in weather for word in ("雨", "雷")):
        tips.append("有降雨，出门带伞并穿防滑的鞋")
    if "晴" in weather:
        tips.append("天气晴朗，注意防晒")

    return f"{city}（{weather}，{data['temperature']}）穿衣建议：" + "；".join(tips) + "。"


if __name__ == "__main__":
    mcp.run()
