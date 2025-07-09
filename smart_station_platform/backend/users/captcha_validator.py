from django.core.cache import cache
from rest_framework import serializers
import time

# 定义一个最小验证时间（秒）
MIN_CAPTCHA_TIME_SECONDS = 1
# 定义容差
TOLERANCE = 10  # 将容差改回一个更合理的值，比如 10


def validate_captcha(data):
    """
    可重用的滑动验证码校验函数，增加了时间和位置验证。
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

    # 5. 兼容性处理和验证
    correct_position = None
    if isinstance(cached_data, dict):
        # --- 新格式数据处理 ---
        correct_position = cached_data.get('position')
        generation_time = cached_data.get('timestamp')

        # 验证时间
        if generation_time:
            time_diff = time.time() - generation_time
            if time_diff < MIN_CAPTCHA_TIME_SECONDS:
                raise serializers.ValidationError({"captcha": "操作过快，请稍后再试。"})
        else:
            # 如果字典里没有时间戳，说明数据异常
            raise serializers.ValidationError({"captcha": "验证码时间戳丢失，请刷新。"})

    elif isinstance(cached_data, int):
        # --- 旧格式数据处理（兼容）---
        # 对于旧格式数据，我们无法进行时间校验，只能跳过
        correct_position = cached_data

    else:
        # --- 未知格式 ---
        raise serializers.ValidationError({"captcha": "验证码数据格式错误，请刷新。"})

    # 6. 最终的位置验证
    if correct_position is None:
        raise serializers.ValidationError({"captcha": "无法获取正确位置，请刷新。"})

    if not (correct_position - TOLERANCE <= user_position <= correct_position + TOLERANCE):
        raise serializers.ValidationError({"captcha": "验证失败，请重试。"})

    # 7. 所有验证通过
    return