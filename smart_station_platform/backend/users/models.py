from django.db import models
from django.contrib.auth.models import AbstractUser
import numpy as np
import base64
import json

# Create your models here.
class UserProfile(AbstractUser):
    GENDER_CHOICES = (
        (0, '保密'),
        (1, '男'),
        (2, '女'),
    )

    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="昵称")
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True, verbose_name="手机号")
    gender = models.IntegerField(choices=GENDER_CHOICES, default=0, verbose_name="性别")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="头像")
    bio = models.TextField(max_length=500, blank=True, null=True, verbose_name="个人简介")

    # [重要] 保持对 auth.Group 和 auth.Permission 的反向关联
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='user_profile_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='user_profile_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    class Meta:
        verbose_name = "用户配置"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username


class FaceData(models.Model):
    """人脸数据模型"""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='face_data', verbose_name="用户")
    face_image = models.ImageField(upload_to='faces/', verbose_name="人脸图像")
    face_encoding = models.TextField(verbose_name="人脸编码数据")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_active = models.BooleanField(default=True, verbose_name="是否有效")
    note = models.CharField(max_length=100, blank=True, null=True, verbose_name="备注")
    
    class Meta:
        verbose_name = "人脸数据"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}的人脸数据 - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def set_face_encoding(self, encoding_array):
        """将numpy数组转换为JSON字符串存储"""
        if isinstance(encoding_array, np.ndarray):
            encoding_list = encoding_array.tolist()
            self.face_encoding = json.dumps(encoding_list)
        else:
            self.face_encoding = json.dumps(encoding_array)
    
    def get_face_encoding(self):
        """将JSON字符串转换回numpy数组"""
        encoding_list = json.loads(self.face_encoding)
        return np.array(encoding_list)


class RegisteredFace(models.Model):
    """注册的人脸信息，用于非用户的人脸识别（如访客、重要人物等）"""
    name = models.CharField(max_length=100, verbose_name="姓名")
    face_image = models.ImageField(upload_to='registered_faces/', verbose_name="人脸图像")
    face_encoding = models.TextField(verbose_name="人脸编码数据")
    category = models.CharField(max_length=50, verbose_name="类别", 
                               default="visitor",
                               choices=[
                                   ("visitor", "访客"),
                                   ("vip", "VIP"),
                                   ("staff", "工作人员"),
                                   ("other", "其他")
                               ])
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_active = models.BooleanField(default=True, verbose_name="是否有效")
    note = models.TextField(blank=True, null=True, verbose_name="备注")
    
    class Meta:
        verbose_name = "注册人脸"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.category}"
    
    def set_face_encoding(self, encoding_array):
        """将numpy数组转换为JSON字符串存储"""
        if isinstance(encoding_array, np.ndarray):
            encoding_list = encoding_array.tolist()
            self.face_encoding = json.dumps(encoding_list)
        else:
            self.face_encoding = json.dumps(encoding_array)
    
    def get_face_encoding(self):
        """将JSON字符串转换回numpy数组"""
        encoding_list = json.loads(self.face_encoding)
        return np.array(encoding_list)