from django.core.cache import cache
from rest_framework import serializers
import time
# 定义一个最小验证时间（秒）
MIN_CAPTCHA_TIME_SECONDS = 1

def validate_captcha(data):
    """
    可重用的滑动验证码校验函数。
    从 data 字典中提取 'captcha_key' 和 'captcha_position'。
    """
    captcha_key = data.get('captcha_key')
    user_position_str = data.get('captcha_position')

    if not captcha_key or not user_position_str:
        raise serializers.ValidationError({"captcha": "验证码参数缺失。"})

    try:
        # 前端传来的可能是字符串，需要转换
        user_position = int(float(user_position_str))
    except (ValueError, TypeError):
        raise serializers.ValidationError({"captcha": "验证码位置参数无效。"})

    cache_key = f"captcha:{captcha_key}"
    # 从缓存中获取整个字典
    cached_data = cache.get(cache_key)
    correct_position = cache.get(cache_key)

    # 无论成功与否，立即删除 key，防止重放攻击
    if correct_position is not None:
        cache.delete(cache_key)

    if correct_position is None:
        raise serializers.ValidationError({"captcha": "验证码已过期或无效，请刷新。"})

        # 增加兼容性判断，处理新旧两种数据格式
    if isinstance(cached_data, dict):
        # 新格式：cached_data 是一个字典
        generation_time = cached_data.get('timestamp')
        correct_position = cached_data.get('position')

        if generation_time:
            time_diff = time.time() - generation_time
            if time_diff < MIN_CAPTCHA_TIME_SECONDS:
                raise serializers.ValidationError({"captcha": "操作过快，请稍后再试。"})

    elif isinstance(cached_data, int):
        # 旧格式：cached_data 是一个整数
        # 对于旧格式数据，我们无法进行时间校验，只能跳过
        correct_position = cached_data

    else:
        # 未知格式，直接报错
        raise serializers.ValidationError({"captcha": "验证码数据格式错误。"})
        # --- 修改结束 ---

        # 检查 correct_position 是否成功获取
    if correct_position is None:
        raise serializers.ValidationError({"captcha": "验证码数据异常，请刷新。"})

    try:
        user_position = int(float(user_position_str))
    except (ValueError, TypeError):
        raise serializers.ValidationError({"captcha": "验证码位置参数无效。"})

    # 允许 ±20 像素的容差
    if not (correct_position - 20 <= user_position <= correct_position + 20):
        raise serializers.ValidationError({"captcha": "验证失败，请重试。"})

    # 校验成功
    return