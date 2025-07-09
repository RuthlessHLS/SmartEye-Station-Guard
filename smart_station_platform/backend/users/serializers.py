# G:\Web\smart_station_platform\backend\users\serializers.py (结构修正版)
from .captcha_validator import validate_captcha
from rest_framework import serializers
from .models import UserProfile
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re

# ==========================================================
# 类 1: UserRegisterSerializer (顶层类)
# ==========================================================
class UserRegisterSerializer(serializers.ModelSerializer):
    """
    用户注册序列化器
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        error_messages={
            'required': '密码是必填项。',
            'blank': '密码不能为空。',
            'min_length': '密码长度不能少于8位。'
        }
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label="确认密码",
        error_messages={
            'required': '请再次输入密码。',
            'blank': '确认密码不能为空。'
        }
    )
    # 接收前端验证码数据的字段
    captcha_key = serializers.CharField(write_only=True, required=True,
                                        error_messages={'required': '验证码key是必填项。'})
    captcha_position = serializers.CharField(write_only=True, required=True,
                                             error_messages={'required': '验证码位置是必填项。'})

    class Meta:
        model = UserProfile
        # 注意：这里的 fields 需要包含 password2 以便接收数据
        fields = ('username', 'password', 'password2', 'email', 'phone_number', 'nickname',
                  'captcha_key', 'captcha_position')

    def validate_username(self, value):
        if UserProfile.objects.filter(username=value).exists():
            raise serializers.ValidationError("该用户名已被占用。")
        if not re.match(r'^[a-zA-Z0-9_]{5,20}$', value):
            raise serializers.ValidationError("用户名必须是5-20位的字母、数字或下划线。")
        return value

    def validate_email(self, value):
        if not value:
            return value
        if UserProfile.objects.filter(email=value).exists():
            raise serializers.ValidationError("这个邮箱地址已经被注册了。")
        return value

    def validate_phone_number(self, value):
        if not value:
            return value
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError("请输入有效的11位手机号码。")
        if UserProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("该手机号已被注册。")
        return value

    def validate(self, data):
        # 1. 校验密码一致性
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "两次输入的密码不一致。"})
        # 2. 调用验证码校验逻辑
        validate_captcha(data)
        # 3. 移除不再需要存入模型的字段
        data.pop('password2')
        data.pop('captcha_key')
        data.pop('captcha_position')

        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data.get('password'))
        user = super().create(validated_data)
        return user

# ==========================================================
# 类 2: UserProfileSerializer (顶层类)
# ==========================================================
class UserProfileSerializer(serializers.ModelSerializer):
    """
    用户个人资料序列化器
    """
    gender = serializers.CharField(source='get_gender_display', read_only=True)
    # avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            'id', 'username', 'email', 'nickname', 'phone_number',
            'gender', 'avatar', 'bio', 'date_joined'
        )
        read_only_fields = ('username', 'date_joined')

# ==========================================================
# 类 3: AvatarUpdateSerializer (顶层类)
# ==========================================================
class AvatarUpdateSerializer(serializers.ModelSerializer):
    """
    用户头像更新序列化器
    """
    class Meta:
        model = UserProfile
        fields = ('avatar',)

# ==========================================================
# 类 4: PasswordResetRequestSerializer (顶层类)
# ==========================================================
class PasswordResetRequestSerializer(serializers.Serializer):
    """
    密码重置请求序列化器
    """
    email = serializers.EmailField(
        error_messages={'required': '邮箱是必填项。', 'blank': '邮箱不能为空。'}
    )

    def validate_email(self, value):
        if not UserProfile.objects.filter(email=value).exists():
            raise serializers.ValidationError("该邮箱未注册。")
        return value

# ==========================================================
# 类 5: PasswordResetConfirmSerializer (顶层类)
# ==========================================================
class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    密码重置确认序列化器
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    uidb64 = serializers.CharField(write_only=True, required=True)
    token = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "两次输入的密码不一致。"})
        # 验证后不再需要 password2
        data.pop('password2')
        return data


# ==========================================================
# 类: MyTokenObtainPairSerializer
# ==========================================================
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    自定义的Token获取序列化器，增加了滑动验证码校验
    """
    captcha_key = serializers.CharField(write_only=True, required=True)
    captcha_position = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        # 先进行验证码校验
        validate_captcha(attrs)

        # 移除验证码字段，然后调用父类的 validate 方法
        attrs.pop('captcha_key', None)
        attrs.pop('captcha_position', None)

        # 调用父类验证逻辑 (验证用户名密码，生成tokens)
        data = super().validate(attrs)
        return data