# users/captcha_generator.py

import random
import io
import base64
from PIL import Image, ImageDraw, ImageFont  # ImageFilter不再需要


def _get_random_color(min_val=100, max_val=255):
    """生成一个随机的、较柔和的颜色"""
    return (random.randint(min_val, max_val), random.randint(min_val, max_val), random.randint(min_val, max_val))


def create_captcha_images():
    """
    [优化版] 生成滑块验证码的背景图、滑块图，并返回其 Base64 编码和正确位置。
    """
    # 定义图片尺寸
    img_size = (300, 150)
    slider_size = 40

    # 1. 创建背景图 (可以直接用一张随机的本地图片做背景，效果更好，性能更高)
    # 为了保持原逻辑，我们还是生成一个颜色背景
    bg_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
    bg_image = Image.new('RGB', img_size, color=bg_color)
    draw = ImageDraw.Draw(bg_image)

    # 2. [优化] 添加噪点，大幅减少数量
    for _ in range(100):  # 从 4500 减少到 100
        x = random.randint(0, img_size[0] - 1)
        y = random.randint(0, img_size[1] - 1)
        draw.point((x, y), fill=_get_random_color(100, 200))

    # 3. 添加干扰线
    for _ in range(5):
        x1, y1 = random.randint(0, img_size[0]), random.randint(0, img_size[1])
        x2, y2 = random.randint(0, img_size[0]), random.randint(0, img_size[1])
        draw.line([(x1, y1), (x2, y2)], fill=_get_random_color(80, 180), width=1)

    # 4. 随机确定滑块位置
    position_x = random.randint(slider_size + 10, img_size[0] - slider_size - 10)
    position_y = random.randint(10, img_size[1] - slider_size - 10)

    # 5. 从背景图中裁剪出滑块区域
    box = (position_x, position_y, position_x + slider_size, position_y + slider_size)
    slider_image_original = bg_image.crop(box)

    # 6. 为滑块添加边框
    slider_draw = ImageDraw.Draw(slider_image_original)
    slider_draw.rectangle([(0, 0), (slider_size - 1, slider_size - 1)], outline=(0, 0, 0), width=1)
    slider_image = slider_image_original

    # 7. [优化] 在背景图上制造缺口 (不再使用高斯模糊)
    # 创建一个半透明的灰色图层来覆盖缺口区域
    gap_layer = Image.new('RGBA', (slider_size, slider_size), (0, 0, 0, 128))  # RGBA, 128是半透明
    bg_image.paste(gap_layer, box, mask=gap_layer)  # 使用 mask 来支持透明度粘贴

    # 在缺口周围画一个轮廓，提示用户
    draw.rectangle(box, outline=(255, 255, 255), width=1)

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