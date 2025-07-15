
import cv2
import numpy as np
from typing import List, Dict, Any

# 为不同的检测类型定义颜色 (B, G, R)
COLOR_MAP = {
    "person": (255, 0, 0),       # 蓝色
    "face": (0, 255, 0),        # 绿色
    "fire": (0, 0, 255),        # 红色
    "smoke": (128, 128, 128),   # 灰色
    "unknown": (0, 255, 255),     # 黄色
    "default": (255, 255, 0)      # 青色
}

def draw_detections(frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
    """
    在视频帧上绘制检测框和标签。

    Args:
        frame (np.ndarray): 要在其上绘制的视频帧 (OpenCV BGR 格式)。
        detections (List[Dict[str, Any]]): AI分析模块返回的检测结果列表。
            每个 detection 字典期望包含:
            - 'box' (List[int]): [x1, y1, x2, y2] 形式的边界框。
            - 'label' (str): 检测到的对象的标签 (例如, 'person', 'fire')。
            - 'confidence' (float, optional): 检测的置信度。
            - 'name' (str, optional): 识别出的人名。

    Returns:
        np.ndarray: 绘制了检测信息的新视频帧。
    """
    if not detections:
        return frame

    # 创建帧的副本以避免修改原始帧
    output_frame = frame.copy()

    for detection in detections:
        # 支持两种格式的检测框: 'box' 或 'bbox'
        box = detection.get('box') or detection.get('bbox')
        if not box or len(box) != 4:
            continue

        x1, y1, x2, y2 = map(int, box)
        # 支持两种格式的标签: 'label' 或 'class_name'
        label = detection.get('label') or detection.get('class_name') or 'unknown'
        label = label.lower()
        confidence = detection.get('confidence')
        # 支持多种格式的身份信息
        name = None
        if 'name' in detection:
            name = detection.get('name')
        elif 'identity' in detection and detection['identity']:
            name = detection['identity'].get('name')

        color = COLOR_MAP.get(label, COLOR_MAP['default'])

        # 绘制边界框
        cv2.rectangle(output_frame, (x1, y1), (x2, y2), color, 2)

        # 准备要显示的文本
        display_text = label.capitalize()
        if name and name != "Unknown":
            display_text = f"{name} ({label})"
        elif confidence is not None:
            display_text = f"{display_text}: {confidence:.2f}"

        # 绘制文本背景
        (text_width, text_height), baseline = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        text_y = y1 - 10 if y1 - 10 > 10 else y1 + text_height + 10
        cv2.rectangle(output_frame, (x1, text_y - text_height - baseline), (x1 + text_width, text_y + baseline), color, -1)

        # 绘制文本
        cv2.putText(output_frame, display_text, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return output_frame 