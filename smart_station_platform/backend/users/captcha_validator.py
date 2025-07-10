from django.core.cache import cache
from rest_framework import serializers
import time

# 定义一个最小验证时间（秒）
MIN_CAPTCHA_TIME_SECONDS = 1
# 定义容差（像素）
TOLERANCE = 20


def validate_captcha(data):
    """
    可重用的滑动验证码校验函数。
    将速度和位置验证合并，作为统一的成功条件。
    """
    captcha_key = data.get('captcha_key')
    user_position_str = data.get('captcha_position')

    if not captcha_key or not user_position_str:
        raise serializers.ValidationError({"captcha": "验证码参数缺失。"})

    # 1. 从缓存中获取数据
    cache_key = f"captcha:{captcha_key}"
    cached_data = cache.get(cache_key)

    # 2. 无论成功与否，立即删除 key 以防重放攻击
    if cached_data is not None:
        cache.delete(cache_key)

    # 3. 检查缓存是否存在
    if cached_data is None:
        raise serializers.ValidationError({"captcha": "验证码已过期或无效，请刷新。"})

    # 4. 解析用户提交的位置
    try:
        user_position = int(float(user_position_str))
    except (ValueError, TypeError):
        raise serializers.ValidationError({"captcha": "验证码位置参数无效。"})

    # 5. 从缓存数据中提取正确位置和时间戳
    correct_position = None
    generation_time = None
    if isinstance(cached_data, dict):
        # 新格式: cached_data 是一个字典
        correct_position = cached_data.get('position')
        generation_time = cached_data.get('timestamp')
    elif isinstance(cached_data, int):
        # 旧格式 (兼容): cached_data 是一个整数 (位置)
        correct_position = cached_data
    else:
        # 未知格式
        raise serializers.ValidationError({"captcha": "验证码数据格式错误，请刷新。"})

    if correct_position is None:
        raise serializers.ValidationError({"captcha": "无法获取正确位置，请刷新。"})

    # 6. 将速度和位置验证合并
    # 6.1 验证位置
    is_position_correct = (correct_position - TOLERANCE <= user_position <= correct_position + TOLERANCE)

    # 6.2 验证时间（仅当时间戳存在时）
    is_time_correct = True  # 默认为 True, 对于没有时间戳的旧数据格式也适用
    if generation_time:
        time_diff = time.time() - generation_time
        if time_diff < MIN_CAPTCHA_TIME_SECONDS:
            is_time_correct = False

    # 7. 最终判定：必须同时满足位置和时间要求
    if not (is_position_correct and is_time_correct):
        raise serializers.ValidationError({"captcha": "验证失败，请重试。"})

    # 8. 所有验证通过
    return