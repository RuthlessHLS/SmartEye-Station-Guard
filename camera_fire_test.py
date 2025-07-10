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

def run_camera_fire_test(camera_id=0, show_enhanced=False):
    """
    打开摄像头并进行实时火焰检测
    
    Args:
        camera_id: 摄像头ID，默认为0（通常是系统默认摄像头）
        show_enhanced: 是否显示增强版本的图像
    """
    print(f"正在打开摄像头 {camera_id} 进行火焰检测测试...")
    
    # 获取资源目录
    asset_base_path = os.getenv("G_DRIVE_ASSET_PATH")
    if not asset_base_path:
        print("警告: 未设置G_DRIVE_ASSET_PATH环境变量，尝试使用默认模型")
    
    # 初始化火焰检测器
    try:
        fire_detector = FlameSmokeDetector()
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
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"摄像头分辨率: {width}x{height}，帧率: {fps}fps")
    
    # 如果要显示增强图像，创建HSV颜色范围
    if show_enhanced:
        # 火焰颜色范围（红色、橙色和黄色）
        # 红色在HSV中有两个范围（低端和高端）
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
    
    # 性能跟踪变量
    frame_count = 0
    total_time = 0
    detection_count = 0
    last_time = time.time()
    fps_display = 0
    
    print("开始实时火焰检测，按 'q' 键退出...")
    
    while True:
        # 读取帧
        ret, frame = cap.read()
        if not ret:
            print("错误: 无法读取摄像头帧")
            break
        
        frame_count += 1
        current_time = time.time()
        
        # 每秒更新一次FPS显示
        if current_time - last_time >= 1.0:
            fps_display = frame_count / (current_time - last_time)
            frame_count = 0
            last_time = current_time
        
        # 创建一个复制版本用于显示
        display_frame = frame.copy()
        
        # 执行火焰检测
        start_time = time.time()
        detections = fire_detector.detect(frame, confidence_threshold=0.3)
        process_time = time.time() - start_time
        total_time += process_time
        
        # 如果有检测结果，绘制到显示帧上
        if detections:
            detection_count += len(detections)
            for det in detections:
                # 提取坐标和类型
                x1, y1, x2, y2 = det["coordinates"]
                det_type = det["type"]
                conf = det["confidence"]
                
                # 根据检测类型设置颜色
                if det_type == "fire":
                    color = (0, 0, 255)  # 红色代表火焰
                elif det_type == "smoke":
                    color = (128, 128, 128)  # 灰色代表烟雾
                else:
                    color = (0, 165, 255)  # 橙色代表火灾相关物体
                
                # 绘制边界框
                cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                
                # 绘制标签背景
                label = f"{det['class_name']} {conf:.2f}"
                text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(display_frame, 
                             (int(x1), int(y1) - text_size[1] - 5),
                             (int(x1) + text_size[0], int(y1)), 
                             color, -1)
                
                # 绘制标签文字
                cv2.putText(display_frame, label, (int(x1), int(y1) - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 如果启用了增强模式，创建增强版本
        if show_enhanced:
            # 创建HSV版本的图像
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
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
            
            # 使用掩码创建增强版本
            enhanced_frame = cv2.bitwise_and(frame, frame, mask=mask)
            
            # 创建并排显示
            h, w = frame.shape[:2]
            combined = np.zeros((h, w*2, 3), dtype=np.uint8)
            combined[:, :w] = display_frame
            combined[:, w:] = enhanced_frame
            
            # 添加标签
            cv2.putText(combined, "Normal", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(combined, "Enhanced", (w+10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            display_frame = combined
        
        # 添加性能信息
        avg_time = total_time / (frame_count if frame_count > 0 else 1)
        info_text = f"FPS: {fps_display:.1f} | 检测: {detection_count} | 处理时间: {process_time*1000:.1f}ms"
        cv2.putText(display_frame, info_text, (10, height-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # 显示帧
        cv2.imshow("火焰检测测试", display_frame)
        
        # 按q键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 释放资源
    cap.release()
    cv2.destroyAllWindows()
    
    # 打印统计信息
    print("\n===== 测试统计 =====")
    print(f"总帧数: {frame_count}")
    print(f"检测到的火焰/烟雾: {detection_count}")
    if frame_count > 0:
        print(f"平均处理时间: {total_time/frame_count*1000:.1f}ms")
        print(f"估计处理速度: {1.0/(total_time/frame_count):.1f}fps")
    
    return True

if __name__ == "__main__":
    # 解析命令行参数
    if len(sys.argv) > 1:
        camera_id = int(sys.argv[1])
    else:
        camera_id = 0
    
    # 询问是否显示增强模式
    show_enhanced = input("是否显示增强模式? (y/n): ").lower() == 'y'
    
    # 运行测试
    run_camera_fire_test(camera_id, show_enhanced) 