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

def enhance_fire_detection(image):
    """
    增强图像中的火焰特征，用于提高检测率
    """
    # 创建HSV版本的图像
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 定义火焰颜色范围 (红色和橙色)
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
    
    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 为原始图像创建副本，用于显示增强效果
    enhanced_image = image.copy()
    
    # 绘制火焰候选区域
    cv2.drawContours(enhanced_image, contours, -1, (0, 0, 255), 2)
    
    # 创建一个增强对比度的图像
    contrast_image = image.copy()
    contrast_image = cv2.convertScaleAbs(contrast_image, alpha=1.5, beta=10)
    
    # 应用伽马校正以增强亮度区域
    gamma = 0.7
    lookup_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    gamma_image = cv2.LUT(image, lookup_table)
    
    # 合并增强的图像
    final_enhanced = cv2.addWeighted(contrast_image, 0.5, gamma_image, 0.5, 0)
    
    # 应用颜色掩码
    color_enhanced = cv2.bitwise_and(final_enhanced, final_enhanced, mask=mask)
    
    # 创建一个4图组展示
    h, w = image.shape[:2]
    quad_display = np.zeros((h*2, w*2, 3), dtype=np.uint8)
    
    # 填充四个象限
    quad_display[0:h, 0:w] = image  # 原始
    quad_display[0:h, w:w*2] = enhanced_image  # 轮廓
    quad_display[h:h*2, 0:w] = final_enhanced  # 对比度增强
    quad_display[h:h*2, w:w*2] = color_enhanced  # 颜色掩码
    
    # 添加标签
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(quad_display, "Original", (10, 30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(quad_display, "Contours", (w+10, 30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(quad_display, "Enhanced", (10, h+30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(quad_display, "Color Mask", (w+10, h+30), font, 0.7, (0, 255, 0), 2)
    
    return {
        'original': image,
        'contours': enhanced_image,
        'enhanced': final_enhanced,
        'color_mask': color_enhanced,
        'quad_display': quad_display
    }

def advanced_fire_detection(image_path):
    """增强的火焰检测功能，特别针对手机屏幕上的火焰图像"""
    print(f"正在进行增强火焰检测，使用图像: {image_path}")
    
    # 检查图像文件是否存在
    if not os.path.exists(image_path):
        print(f"错误: 图像文件 '{image_path}' 不存在")
        return False
    
    # 读取图像
    original_image = cv2.imread(image_path)
    if original_image is None:
        print(f"错误: 无法读取图像文件 '{image_path}'")
        return False
    
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
    
    # 获取图像增强版本
    enhanced_images = enhance_fire_detection(original_image)
    
    # 在各种版本的图像上进行检测
    detection_results = {}
    
    for key, img in enhanced_images.items():
        if key != 'quad_display':  # 跳过四象限图像
            print(f"\n对 {key} 图像进行检测...")
            start_time = time.time()
            detections = fire_detector.detect(img, confidence_threshold=0.25)  # 使用较低的置信度
            elapsed_time = time.time() - start_time
            
            detection_results[key] = {
                'detections': detections,
                'time': elapsed_time
            }
            
            print(f"  检测完成，耗时 {elapsed_time:.3f} 秒")
            print(f"  检测到 {len(detections)} 个火焰/烟雾对象:")
            
            for i, det in enumerate(detections):
                print(f"    {i+1}. 类型: {det['type']}, 类别: {det['class_name']}, 置信度: {det['confidence']:.3f}")
            
            # 绘制检测结果
            processed_img, _ = fire_detector.process_video_frame(img, confidence_threshold=0.25, draw_result=True)
            enhanced_images[f"{key}_detected"] = processed_img
    
    # 显示原始和增强后的图像
    cv2.imshow("火焰检测增强 - 四象限视图", enhanced_images['quad_display'])
    
    # 创建检测结果视图
    detection_quad = np.zeros((original_image.shape[0]*2, original_image.shape[1]*2, 3), dtype=np.uint8)
    
    # 填充检测结果
    h, w = original_image.shape[:2]
    if 'original_detected' in enhanced_images:
        detection_quad[0:h, 0:w] = enhanced_images['original_detected']
    if 'contours_detected' in enhanced_images:
        detection_quad[0:h, w:w*2] = enhanced_images['contours_detected']
    if 'enhanced_detected' in enhanced_images:
        detection_quad[h:h*2, 0:w] = enhanced_images['enhanced_detected']
    if 'color_mask_detected' in enhanced_images:
        detection_quad[h:h*2, w:w*2] = enhanced_images['color_mask_detected']
    
    # 添加标签
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(detection_quad, "Original Det", (10, 30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(detection_quad, "Contours Det", (w+10, 30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(detection_quad, "Enhanced Det", (10, h+30), font, 0.7, (0, 255, 0), 2)
    cv2.putText(detection_quad, "Color Mask Det", (w+10, h+30), font, 0.7, (0, 255, 0), 2)
    
    cv2.imshow("火焰检测结果 - 四象限视图", detection_quad)
    
    print("\n===== 检测结果总结 =====")
    best_version = None
    max_detections = 0
    
    for key, result in detection_results.items():
        num_detections = len(result['detections'])
        if num_detections > max_detections:
            max_detections = num_detections
            best_version = key
            
        print(f"{key}图像: 检测到{num_detections}个火焰/烟雾对象，耗时{result['time']:.3f}秒")
    
    if best_version:
        print(f"\n最佳检测结果来自: {best_version}图像，检测到{max_detections}个火焰/烟雾对象")
        
        if max_detections > 0:
            highest_conf = max([det['confidence'] for det in detection_results[best_version]['detections']])
            print(f"最高置信度: {highest_conf:.3f}")
        
    # 等待按键
    print("\n按任意键关闭窗口...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return max_detections > 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 使用命令行参数提供的图像路径
        image_path = sys.argv[1]
    else:
        # 默认使用示例图像
        image_path = input("请输入火焰图像的路径: ")
    
    advanced_fire_detection(image_path) 