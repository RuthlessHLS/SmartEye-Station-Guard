# G:\Web\smart_station_platform\backend\users\serializers.py (结构修正版)
from .captcha_validator import validate_captcha
from rest_framework import serializers
from .models import UserProfile, FaceData, RegisteredFace
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re
from django.contrib.auth import get_user_model

User = get_user_model()

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
    用户个人资料序列化器 (读写)
    """
    # gender现在只读，我们通过 gender_code 来写入
    gender = serializers.CharField(source='get_gender_display', read_only=True)
    # 添加一个可写的字段用于接收前端传来的整数值
    gender_code = serializers.IntegerField(source='gender', write_only=True, required=False)

    class Meta:
        model = UserProfile
        fields = (
            'id', 'username', 'email', 'nickname', 'phone_number',
            'gender', 'gender_code', 'avatar', 'bio', 'date_joined'
        )
        # username 和 date_joined 在任何情况下都只读
        read_only_fields = ('username', 'date_joined', 'email')
        # 定义 write_only 字段
        extra_kwargs = {
            'gender_code': {'write_only': True},
        }

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
# 类6: MyTokenObtainPairSerializer
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

        # 重命名token字段以匹配前端期望的格式
        data['token'] = data.pop('access')
        data['refresh_token'] = data.pop('refresh')

        # 添加用户信息到响应中
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'nickname': getattr(user, 'nickname', None),
            'phone_number': getattr(user, 'phone_number', None),
        }

        return data


# ==========================================================
# 类 7: UserAdminSerializer
# ==========================================================
class UserAdminSerializer(serializers.ModelSerializer):
    """
    管理员用于管理用户的序列化器。
    - 创建用户时，密码是必填的。
    - 更新用户时，密码是可选的（留空则不修改）。
    - 密码字段只写不读，不会在 API 响应中返回。
    """
    password = serializers.CharField(
        write_only=True,
        required=False,  # 更新时不是必填项
        allow_blank=True,
        style={'input_type': 'password'},
        min_length=8,
        help_text="仅在创建用户或重置密码时填写。更新用户信息时若留空，则不修改密码。"
    )

    class Meta:
        model = UserProfile
        # 定义管理员可以查看和修改的字段
        fields = (
            'id', 'username', 'email', 'nickname', 'phone_number',
            'is_staff', 'is_active', 'password'
        )
        # 定义只读字段，防止在列表视图中被意外修改
        read_only_fields = ('id',)

    def validate_password(self, value):
        # 即使密码字段 allow_blank=True，我们也不希望存入一个空字符串
        if value == '':
            return None
        return value

    def create(self, validated_data):
        """
        创建用户时，必须提供密码，并对其进行哈希处理。
        """
        # 从验证数据中提取密码
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({'password': '创建用户时必须提供密码。'})

        # 使用 make_password 对密码进行哈希
        validated_data['password'] = make_password(password)
        user = super().create(validated_data)
        return user

    def update(self, instance, validated_data):
        """
        更新用户时，如果提供了密码，则更新密码，否则保持原样。
        """
        # 弹出密码字段，单独处理
        password = validated_data.pop('password', None)

        if password:
            # 如果提供了新密码，则设置新密码
            instance.set_password(password)

        # 调用父类的 update 方法更新其他字段
        # instance 会被传入，所以其他字段会更新到这个实例上
        user = super().update(instance, validated_data)

        # 如果密码被更新，需要保存实例
        if password:
            user.save()

        return user

# ==========================================================
# 类 8: UserDirectorySerializer
# ==========================================================
class UserDirectorySerializer(serializers.ModelSerializer):
    """
    用于公开用户目录的序列化器。
    - 只读。
    - 只暴露 id, username, phone_number, email。
    """
    class Meta:
        model = UserProfile
        fields = ('id', 'username', 'phone_number', 'email', 'nickname')


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'nickname', 'phone_number', 'gender', 'avatar', 'bio']
        read_only_fields = ['id']

class FaceDataSerializer(serializers.ModelSerializer):
    """人脸数据序列化器"""
    face_image_url = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    
    class Meta:
        model = FaceData
        fields = ['id', 'user', 'username', 'face_image', 'face_image_url', 'created_at', 'is_active', 'note']
        read_only_fields = ['id', 'created_at', 'face_encoding', 'face_image_url']
        extra_kwargs = {
            'face_encoding': {'write_only': True}  # 不在API响应中返回人脸编码数据
        }
    
    def get_face_image_url(self, obj):
        """获取完整图片URL"""
        if obj.face_image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.face_image.url)
            return obj.face_image.url
        return None
    
    def get_username(self, obj):
        """获取用户名"""
        return obj.user.username

class RegisteredFaceSerializer(serializers.ModelSerializer):
    """已注册人脸序列化器"""
    face_image_url = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    
    class Meta:
        model = RegisteredFace
        fields = ['id', 'name', 'face_image', 'face_image_url', 'category', 
                  'category_display', 'created_at', 'is_active', 'note']
        read_only_fields = ['id', 'created_at', 'face_encoding', 'face_image_url']
        extra_kwargs = {
            'face_encoding': {'write_only': True}  # 不在API响应中返回人脸编码数据
        }
    
    def get_face_image_url(self, obj):
        """获取完整图片URL"""
        if obj.face_image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.face_image.url)
            return obj.face_image.url
        return None
    
    def get_category_display(self, obj):
        """获取类别显示名"""
        return obj.get_category_display()

# ==========================================================
#  类 9: PasswordChangeSerializer
# ==========================================================
class PasswordChangeSerializer(serializers.Serializer):
    """
    修改密码序列化器
    """
    current_password = serializers.CharField(style={"input_type": "password"}, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, required=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("当前密码不正确。")
        return value

#  类 9: PasswordChangeSerializer
# ==========================================================
class PasswordChangeSerializer(serializers.Serializer):
    """
    修改密码序列化器
    """
    current_password = serializers.CharField(style={"input_type": "password"}, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, required=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("当前密码不正确。")
        return value


