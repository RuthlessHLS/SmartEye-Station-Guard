# users/captcha_generator.py

import random
import io
import base64
from PIL import Image, ImageDraw, ImageFilter


def _get_random_color():
    """生成一个随机的、较柔和的颜色"""
    return (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))


def create_captcha_images():
    """
    生成滑块验证码的背景图、滑块图，并返回其 Base64 编码和正确位置。

    :return: 一个包含以下键的字典:
        - 'background_base64': 背景图的 Base64 编码字符串。
        - 'slider_base64': 滑块图的 Base64 编码字符串。
        - 'position_x': 滑块在 x 轴上的正确位置（像素）。
        - 'position_y': 滑块在 y 轴上的正确位置（像素）。
    """
    # 定义图片尺寸
    img_size = (300, 150)
    slider_size = 40

    # 1. 创建背景图
    bg_color = _get_random_color()
    bg_image = Image.new('RGB', img_size, color=bg_color)
    draw = ImageDraw.Draw(bg_image)

    # 2. 添加噪点
    for _ in range(int(img_size[0] * img_size[1] * 0.1)):  # 10% 的噪点
        x = random.randint(0, img_size[0] - 1)
        y = random.randint(0, img_size[1] - 1)
        draw.point((x, y), fill=_get_random_color())

    # 3. 添加干扰线
    for _ in range(5):
        x1, y1 = random.randint(0, img_size[0]), random.randint(0, img_size[1])
        x2, y2 = random.randint(0, img_size[0]), random.randint(0, img_size[1])
        draw.line([(x1, y1), (x2, y2)], fill=_get_random_color(), width=1)

    # 4. 随机确定滑块位置
    # 确保滑块不会太靠边
    position_x = random.randint(slider_size + 10, img_size[0] - slider_size - 10)
    position_y = random.randint(10, img_size[1] - slider_size - 10)

    # 5. 从背景图中裁剪出滑块区域
    box = (position_x, position_y, position_x + slider_size, position_y + slider_size)
    slider_image_original = bg_image.crop(box)

    # 6. 为滑块添加边框，使其更醒目
    slider_draw = ImageDraw.Draw(slider_image_original)
    slider_draw.rectangle([(0, 0), (slider_size - 1, slider_size - 1)], outline=(0, 0, 0))  # 黑色边框
    slider_image = slider_image_original

    # 7. 在背景图上制造缺口
    # 复制一块区域，对其进行模糊处理，再贴回去
    gap_area = bg_image.crop(box)
    gap_area_blurred = gap_area.filter(ImageFilter.GaussianBlur(radius=3))  # 高斯模糊
    bg_image.paste(gap_area_blurred, box)

    # 在缺口周围画一个轮廓，提示用户
    draw.rectangle(box, outline=(255, 255, 255))  # 白色轮廓

    # 8. 将图片转为 Base64
    bg_io = io.BytesIO()
    bg_image.save(bg_io, format='PNG')
    background_base64 = base64.b64encode(bg_io.getvalue()).decode()

    slider_io = io.BytesIO()
    slider_image.save(slider_io, format='PNG')
    slider_base64 = base64.b64encode(slider_io.getvalue()).decode()

    return {
        'background_base64': background_base64,
        'slider_base64': slider_base64,
        'position_x': position_x,
        'position_y': position_y,
    }