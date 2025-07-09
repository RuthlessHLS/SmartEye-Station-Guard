from django.core.cache import cache
from rest_framework import serializers

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
    correct_position = cache.get(cache_key)

    # 无论成功与否，立即删除 key，防止重放攻击
    if correct_position is not None:
        cache.delete(cache_key)

    if correct_position is None:
        raise serializers.ValidationError({"captcha": "验证码已过期或无效，请刷新。"})

    # 允许 ±20 像素的容差
    if not (correct_position - 20 <= user_position <= correct_position + 20):
        raise serializers.ValidationError({"captcha": "验证失败，请重试。"})

    # 校验成功
    return