from django.db import models
from django.contrib.auth.models import AbstractUser

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