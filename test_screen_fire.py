import os
import sys
import cv2
import numpy as np
import time

# 添加AI服务目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
ai_service_dir = os.path.join(current_dir, 'smart_station_platform', 'ai_service')
sys.path.append(ai_service_dir)

from core.fire_smoke_detection import FlameSmokeDetector

def screen_fire_test(camera_id=0, confidence=0.2):
    """
    专门针对手机屏幕上显示的火焰图片进行测试
    
    Args:
        camera_id: 摄像头ID，默认为0
        confidence: 置信度阈值，默认设置非常低(0.2)以确保能捕获到微弱的火焰特征
    """
    print(f"正在启动手机屏幕火焰测试，使用摄像头ID: {camera_id}")
    print(f"置信度阈值设置为: {confidence}")
    
    # 初始化火焰检测器
    try:
        detector = FlameSmokeDetector()
        print("火焰检测器初始化成功")
    except Exception as e:
        print(f"错误: 无法初始化火焰检测器: {e}")
        return False
    
    # 打开摄像头
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"错误: 无法打开摄像头 {camera_id}")
        return False
    
    # 获取摄像头分辨率
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头分辨率: {width}x{height}")
    
    # 创建窗口
    cv2.namedWindow("原始图像", cv2.WINDOW_NORMAL)
    cv2.namedWindow("HSV掩码", cv2.WINDOW_NORMAL)
    cv2.namedWindow("检测结果", cv2.WINDOW_NORMAL)
    cv2.namedWindow("增强图像", cv2.WINDOW_NORMAL)
    
    print("开始测试，按 'q' 键退出")
    
    detection_count = 0
    last_time = time.time()
    frame_count = 0
    
    while True:
        # 读取帧
        ret, frame = cap.read()
        if not ret:
            print("无法读取摄像头帧")
            break
        
        frame_count += 1
        
        # 显示原始图像
        cv2.imshow("原始图像", frame)
        
        # 创建HSV版本并提取火焰颜色
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 定义火焰颜色范围
        # 红色在HSV中有两个范围
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        
        # 橙色范围
        lower_orange = np.array([10, 100, 100])
        upper_orange = np.array([25, 255, 255])
        
        # 黄色范围
        lower_yellow = np.array([25, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        
        # 创建掩码
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # 合并掩码
        mask = mask_red1 + mask_red2 + mask_orange + mask_yellow
        
        # 对掩码应用腐蚀和膨胀以消除噪点
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 应用掩码到原始图像
        fire_mask = cv2.bitwise_and(frame, frame, mask=mask)
        cv2.imshow("HSV掩码", fire_mask)
        
        # 增强图像对比度和亮度
        enhanced = frame.copy()
        enhanced = cv2.convertScaleAbs(enhanced, alpha=1.5, beta=10)
        
        # 应用伽马校正以增强亮度区域
        gamma = 0.7
        lookup_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, lookup_table)
        
        cv2.imshow("增强图像", enhanced)
        
        # 尝试同时检测原始图像和增强图像
        detections_original = detector.detect(frame, confidence_threshold=confidence)
        detections_enhanced = detector.detect(enhanced, confidence_threshold=confidence)
        detections_mask = detector.detect(fire_mask, confidence_threshold=confidence)
        
        # 合并检测结果
        all_detections = detections_original + detections_enhanced + detections_mask
        
        # 移除重复的检测框
        unique_detections = []
        for det in all_detections:
            is_duplicate = False
            for unique_det in unique_detections:
                # 简单的IoU计算：如果两个框有50%以上的重叠，认为是同一个物体
                box1 = det["coordinates"]
                box2 = unique_det["coordinates"]
                
                # 计算交集
                x_left = max(box1[0], box2[0])
                y_top = max(box1[1], box2[1])
                x_right = min(box1[2], box2[2])
                y_bottom = min(box1[3], box2[3])
                
                if x_right < x_left or y_bottom < y_top:
                    continue
                
                intersection_area = (x_right - x_left) * (y_bottom - y_top)
                box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
                box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
                
                iou = intersection_area / (box1_area + box2_area - intersection_area)
                
                if iou > 0.5:
                    is_duplicate = True
                    # 保留置信度更高的
                    if det["confidence"] > unique_det["confidence"]:
                        unique_det.update(det)
                    break
            
            if not is_duplicate:
                unique_detections.append(det)
        
        # 添加颜色检测
        if not unique_detections:
            # 检查火焰颜色覆盖率
            coverage = cv2.countNonZero(mask) / (frame.shape[0] * frame.shape[1])
            if coverage > 0.05:  # 如果火焰颜色覆盖超过5%
                h, w = frame.shape[:2]
                # 创建一个覆盖整个图像的检测框
                unique_detections.append({
                    "type": "fire",
                    "class_name": "fire_color_detected",
                    "confidence": 0.6,
                    "coordinates": [0, 0, w, h],
                    "center": [w/2, h/2],
                    "area": w*h
                })
        
        # 显示检测结果
        result_frame = frame.copy()
        if unique_detections:
            detection_count += 1
            print(f"检测到 {len(unique_detections)} 个火焰/烟雾对象:")
            
            for i, det in enumerate(unique_detections):
                # 提取坐标和类型
                x1, y1, x2, y2 = [int(c) for c in det["coordinates"]]
                det_type = det["type"]
                conf = det["confidence"]
                class_name = det["class_name"]
                
                print(f"  {i+1}. 类型: {det_type}, 类别: {class_name}, 置信度: {conf:.3f}")
                
                # 根据检测类型设置颜色
                if det_type == "fire":
                    color = (0, 0, 255)  # 红色代表火焰
                elif det_type == "smoke":
                    color = (128, 128, 128)  # 灰色代表烟雾
                else:
                    color = (0, 165, 255)  # 橙色代表火灾相关物体
                
                # 绘制边界框
                cv2.rectangle(result_frame, (x1, y1), (x2, y2), color, 2)
                
                # 绘制标签背景
                label = f"{class_name} {conf:.2f}"
                text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(result_frame, 
                             (x1, y1 - text_size[1] - 5),
                             (x1 + text_size[0], y1), 
                             color, -1)
                
                # 绘制标签文字
                cv2.putText(result_frame, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 显示结果
        cv2.imshow("检测结果", result_frame)
        
        # 每秒打印一次状态
        current_time = time.time()
        if current_time - last_time >= 1.0:
            fps = frame_count / (current_time - last_time)
            print(f"FPS: {fps:.1f} | 检测率: {detection_count/frame_count:.2f}")
            detection_count = 0
            frame_count = 0
            last_time = current_time
        
        # 按q退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 清理资源
    cap.release()
    cv2.destroyAllWindows()
    
    return True

if __name__ == "__main__":
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="手机屏幕火焰检测测试")
    parser.add_argument("--camera", type=int, default=0, help="摄像头ID")
    parser.add_argument("--confidence", type=float, default=0.2, help="置信度阈值")
    args = parser.parse_args()
    
    # 运行测试
    screen_fire_test(args.camera, args.confidence) 