
import cv2
import numpy as np
from typing import List, Dict, Any

# 为不同的检测类型定义颜色 (B, G, R)
# 如需扩展，可在此字典中添加新的行为或标签。
COLOR_MAP = {
    "person": (255, 0, 0),          # 蓝色
    "active": (255, 0, 0),          # 与 person 相同，表示正常活动
    "face": (0, 255, 0),            # 绿色
    "fire": (0, 0, 255),            # 红色
    "smoke": (128, 128, 128),       # 灰色
    "fall_down": (0, 0, 255),
    "waving_hand": (0, 0, 255),
    "fighting": (0, 0, 255),
    "fighting_suspicious": (0, 165, 255),  # 橙色
    "unknown": (0, 255, 255),       # 黄色 (未知物体)
    "unknown_person": (0, 0, 255),  # 未知人员 -> 红色
    "smoking": (0, 128, 255),      # 抽烟 -> 橙蓝
    "default": (255, 255, 0)        # 青色
}

# 针对不同检测类别/行为的最低置信度阈值
CONF_THRESHOLD_MAP = {
    "fire": 0.5,
    "fall_down": 0.4,
    "fighting": 0.5,
    "fighting_suspicious": 0.4,
    "waving_hand": 0.4,
    "unknown_person": 0.01,  # 未知人员始终显示
    "smoking": 0.4,
    # 其它类别默认 0.3
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

    # 在传入帧上直接绘制，调用方通常已经传入了 frame.copy()，可减少一次深拷贝
    output_frame = frame

    for detection in detections:
        # ------------------ 解析检测框 ------------------
        # 既支持单框 (box/bbox/coordinates)，也支持多框 (boxes)。
        boxes: List[Any] = []
        if 'boxes' in detection and isinstance(detection['boxes'], list):
            boxes = detection['boxes']
        else:
            single_box = detection.get('box') or detection.get('bbox') or detection.get('coordinates')
            if single_box:
                boxes = [single_box]

        if not boxes:
            continue

        # ------------------ 解析标签 ------------------
        # 解析 label / behavior
        label = (
            detection.get('label')
            or detection.get('class_name')
            or detection.get('behavior')
            or 'unknown'
        )
        label = str(label).lower()

        # 将 'cigarette' 归一化为 'smoking'
        if label == 'cigarette':
            label = 'smoking'

        # 对 'active' 也绘制框，只是不标记为异常

        # 修正：只要是人脸且未知，强制label为unknown_person
        if label == 'face':
            person_name = None
            is_known = True
            if 'name' in detection:
                person_name = detection.get('name')
            elif 'identity' in detection and detection['identity']:
                person_name = detection['identity'].get('name')
                is_known = detection['identity'].get('is_known', True)
            if person_name is None or str(person_name).lower() == 'unknown' or is_known is False:
                label = 'unknown_person'
                detection['is_abnormal'] = True  # 强制高亮

        # 其它类型也可按需补充

        confidence = detection.get('confidence', 1.0)

        # -------- 跳过纯 'active' 行为，其余均绘制 --------
        if label == 'active' and not detection.get('is_abnormal'):
            continue

        # --- 置信度过滤 ---
        min_conf = CONF_THRESHOLD_MAP.get(label, 0.3)
        if confidence < min_conf:
            continue  # 低于阈值，不绘制

        # 支持多种格式的身份信息
        name = None
        if 'name' in detection:
            name = detection.get('name')
        elif 'identity' in detection and detection['identity']:
            name = detection['identity'].get('name')

        # 终极兜底：只要未知就红框+陌生人
        is_unknown = (
            label == 'unknown_person' or
            (name and (name.lower() in ['unknown', 'none'] or '?' in str(name))) or
            (not name and (label.lower() in ['unknown', 'none'] or '?' in label))
        )
        # DEBUG日志
        print('DEBUG_DRAW:', label, name, is_unknown, detection)

        # ------------------ 绘制每一个框 ------------------
        for box in boxes:
            if not box or len(box) != 4:
                continue

            x1, y1, x2, y2 = map(int, box)

            # 优先使用 is_abnormal 或 unknown_person 来决定颜色
            if detection.get('is_abnormal') or label == 'unknown_person':
                color = (0, 0, 255)  # 红色
            else:
                color = COLOR_MAP.get(label, COLOR_MAP['default'])

            # 绘制边界框
            cv2.rectangle(output_frame, (x1, y1), (x2, y2), color, 2)

            # -------- 绘制文字描述 --------
            if label == 'unknown_person':
                text = '陌生人'
            elif name and name != "Unknown" and name.count('?') < 2 and name.lower() not in ['unknown', 'none', '']:
                text = f"{name}"
            else:
                text = label
            # 更强兜底：只要text是问号、空、unknown、none，都显示“陌生人”
            if not text or text.count('?') >= 1 or text.strip('?').strip() == '' or text.lower() in ['unknown', 'none']:
                text = '陌生人'

            # 在置信度足够高时追加百分比
            if confidence is not None:
                text += f" {confidence:.2f}"

            text_x, text_y = x1, max(y1 - 5, 15)

            # 异常目标使用红色文字，否则使用白色文字
            text_color = (0, 0, 255) if detection.get("is_abnormal") else (255, 255, 255)

            cv2.putText(
                output_frame,
                text,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                1,
            )

            # 若存在 group_box (打架聚合框)，绘制粗红色虚线框
            if 'group_box' in detection and detection['group_box']:
                gb = list(map(int, detection['group_box']))
                # 使用 openCV 绘制虚线: 逐段线
                gb_color = (0, 0, 255)
                thickness = 3
                dash_len = 10
                x1g, y1g, x2g, y2g = gb
                # 顶边
                for x in range(x1g, x2g, dash_len*2):
                    cv2.line(output_frame, (x, y1g), (min(x+dash_len, x2g), y1g), gb_color, thickness)
                # 底边
                for x in range(x1g, x2g, dash_len*2):
                    cv2.line(output_frame, (x, y2g), (min(x+dash_len, x2g), y2g), gb_color, thickness)
                # 左边
                for y in range(y1g, y2g, dash_len*2):
                    cv2.line(output_frame, (x1g, y), (x1g, min(y+dash_len, y2g)), gb_color, thickness)
                # 右边
                for y in range(y1g, y2g, dash_len*2):
                    cv2.line(output_frame, (x2g, y), (x2g, min(y+dash_len, y2g)), gb_color, thickness)

    return output_frame 

def draw_zones(frame: np.ndarray, zones: List[Dict[str, Any]], color: tuple = (0, 255, 255)) -> np.ndarray:
    """在帧上绘制危险区域多边形。

    Args:
        frame: OpenCV BGR 格式帧
        zones: 区域列表，每个元素需包含 'coordinates': [[x1,y1], [x2,y2], ...]
        color: 线条颜色 (默认黄色)
    Returns:
        绘制后的帧副本
    """
    if not zones:
        return frame

    output = frame.copy()
    for zone in zones:
        coords = zone.get('coordinates') or zone.get('points') or []
        if not coords or len(coords) < 3:
            continue
        pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(output, [pts], isClosed=True, color=color, thickness=2)
    return output 