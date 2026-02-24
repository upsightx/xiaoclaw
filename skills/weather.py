#!/usr/bin/env python3
"""Weather Skill for xiaoclaw"""

def get_weather(location: str = "Shanghai", **kwargs) -> str:
    return f"🌤️ {location}: 晴, 22°C, 湿度65%"

def get_forecast(location: str = "Shanghai", days: int = 3, **kwargs) -> str:
    forecasts = ["☀️ 晴", "⛅ 多云", "🌧️ 小雨"]
    return "\n".join([f"Day{i+1}: {forecasts[i]}" for i in range(min(days,3))])

def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("weather", "天气查询", {"weather": get_weather, "forecast": get_forecast})

skill = get_skill()
