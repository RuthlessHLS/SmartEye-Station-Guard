from django.test import TestCase

# Create your tests here.
# users/tests.py

from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
import json

# 假设你的 captcha_validator 在 users.captcha_validator
from .captcha_validator import validate_captcha, serializers


# Create your tests here.
class CaptchaTests(TestCase):

    def setUp(self):
        """在每个测试开始前运行"""
        self.client = Client()
        self.generate_url = reverse('captcha_generate')  # 确保你的 urls.py 中有名为 'captcha_generate' 的路由

    def tearDown(self):
        """在每个测试结束后清理缓存"""
        cache.clear()

    def test_generate_captcha_api(self):
        """
        测试 /captcha/generate/ 接口是否能成功返回数据。
        """
        response = self.client.get(self.generate_url)

        # 1. 检查 HTTP 状态码是否为 200 OK
        self.assertEqual(response.status_code, 200)

        # 2. 检查返回的 JSON 数据结构是否正确
        data = response.json()
        self.assertIn('captcha_key', data)
        self.assertIn('background_image', data)
        self.assertIn('slider_image', data)
        self.assertIn('slider_y', data)

        # 3. 检查 Base64 图片头是否正确
        self.assertTrue(data['background_image'].startswith('data:image/png;base64,'))
        self.assertTrue(data['slider_image'].startswith('data:image/png;base64,'))

        # 4. 检查答案是否已存入缓存
        cache_key = f"captcha:{data['captcha_key']}"
        self.assertIsNotNone(cache.get(cache_key), "正确答案没有被存入缓存")

    def test_validate_captcha_success(self):
        """
        测试 validate_captcha 函数：成功的场景。
        """
        captcha_key = 'test_success_key'
        correct_position = 150
        cache_key = f"captcha:{captcha_key}"

        # 模拟设置缓存
        cache.set(cache_key, correct_position, timeout=60)

        # 模拟前端传来的数据 (在容差范围内)
        data = {'captcha_key': captcha_key, 'captcha_position': str(correct_position + 3)}

        # 调用验证函数，不应该抛出任何异常
        try:
            validate_captcha(data)
        except serializers.ValidationError as e:
            self.fail(f"验证码校验失败，不应抛出异常: {e.detail}")

        # 验证成功后，缓存应该被删除（防重放）
        self.assertIsNone(cache.get(cache_key), "验证成功后，缓存的 key 没有被删除")

    def test_validate_captcha_failure_wrong_position(self):
        """
        测试 validate_captcha 函数：位置错误的场景。
        """
        captcha_key = 'test_failure_key'
        correct_position = 150
        cache_key = f"captcha:{captcha_key}"

        cache.set(cache_key, correct_position, timeout=60)

        # 模拟前端传来的错误数据 (超出容差范围)
        data = {'captcha_key': captcha_key, 'captcha_position': str(correct_position + 10)}

        # 使用 assertRaises 来断言会抛出 ValidationError
        with self.assertRaises(serializers.ValidationError) as cm:
            validate_captcha(data)

        # 检查错误信息是否符合预期
        self.assertEqual(cm.exception.detail['captcha'], "验证失败，请重试。")

        # 验证失败后，缓存也应该被删除
        self.assertIsNone(cache.get(cache_key), "验证失败后，缓存的 key 没有被删除")

    def test_validate_captcha_expired(self):
        """
        测试 validate_captcha 函数：验证码已过期的场景。
        """
        data = {'captcha_key': 'non_existent_key', 'captcha_position': '150'}

        with self.assertRaises(serializers.ValidationError) as cm:
            validate_captcha(data)

        self.assertEqual(cm.exception.detail['captcha'], "验证码已过期或无效，请刷新。")

    def test_validate_captcha_replay_attack(self):
        """
        测试 validate_captcha 函数：防止重放攻击。
        """
        captcha_key = 'test_replay_key'
        correct_position = 150
        cache_key = f"captcha:{captcha_key}"
        cache.set(cache_key, correct_position, timeout=60)

        data = {'captcha_key': captcha_key, 'captcha_position': str(correct_position)}

        # 第一次验证，应该成功
        validate_captcha(data)

        # 第二次使用相同的 key 进行验证，应该失败（因为 key 已被删除）
        with self.assertRaises(serializers.ValidationError) as cm:
            validate_captcha(data)

        self.assertEqual(cm.exception.detail['captcha'], "验证码已过期或无效，请刷新。")