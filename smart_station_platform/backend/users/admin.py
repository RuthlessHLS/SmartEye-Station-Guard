from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile
from django.utils.translation import gettext_lazy as _

# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    # 1. 后台列表页显示哪些字段
    # 我们添加了 'phone_number' 和 'nickname'
    list_display = ('username', 'email', 'nickname', 'phone_number', 'is_staff')

    # 2. 列表页的链接字段
    # list_display_links = ('username', 'nickname') # 可以让昵称也成为可点击的链接

    # 3. 搜索字段
    # 添加 'nickname' 和 'phone_number' 到可搜索范围
    search_fields = ('username', 'email', 'nickname', 'phone_number')

    # 4. 过滤器
    # 添加 'gender' 作为过滤器
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'gender')

    # 5. [最重要] 用户编辑页面的字段布局
    # UserAdmin.fieldsets 是一个定义好的布局，我们需要对其进行扩展
    # 我们将自定义字段添加到一个新的分区 "个人信息" 中

    # 继承并扩展原有的 fieldsets
    # UserAdmin.fieldsets 结构：
    # (None, {"fields": ("username", "password")}),
    # (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
    # (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    # (_("Important dates"), {"fields": ("last_login", "date_joined")}),

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        # 在 "Personal info" 分区中加入我们的新字段
        (_("Personal info"),
         {"fields": ("first_name", "last_name", "email", "nickname", "phone_number", "gender", "avatar", "bio")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # 如果你希望在用户创建页面也显示这些自定义字段，需要修改 add_fieldsets
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Custom Fields'), {'fields': ('nickname', 'phone_number', 'gender', 'avatar', 'bio')}),
    )