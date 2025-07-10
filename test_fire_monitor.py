"""
火焰检测监控测试脚本
用于测试AI智能站点守护中的火焰检测功能

这个脚本会模拟一个简单的火焰场景并发送到AI服务进行检测
"""

import cv2
import numpy as np
import requests
import time
import base64
import json
import os
from PIL import Image, ImageDraw
from io import BytesIO

# 服务地址
AI_SERVICE_URL = "http://localhost:8001/frame/analyze/"

def create_test_fire_image():
    """创建一个带有模拟火焰的测试图像"""
    # 创建黑色背景
    width, height = 640, 480
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 添加房间元素
    # 墙壁
    cv2.rectangle(image, (0, 0), (width, height), (120, 120, 120), -1)
    # 地板
    cv2.rectangle(image, (0, height//2), (width, height), (80, 50, 20), -1)
    # 窗户
    cv2.rectangle(image, (50, 50), (200, 200), (200, 200, 255), -1)
    # 桌子
    cv2.rectangle(image, (300, 300), (500, 350), (30, 20, 10), -1)
    
    # 创建火焰效果
    fire_center_x, fire_center_y = 400, 280
    fire_width, fire_height = 80, 100
    
    # 创建渐变火焰
    for y in range(fire_center_y - fire_height//2, fire_center_y + fire_height//2):
        for x in range(fire_center_x - fire_width//2, fire_center_x + fire_width//2):
            if 0 <= x < width and 0 <= y < height:
                # 火焰中心到当前点的距离
                dx = x - fire_center_x
                dy = y - fire_center_y
                distance = np.sqrt(dx**2 + dy**2)
                
                # 火焰颜色计算（距离越近越黄白，越远越红）
                if distance < fire_width/3:
                    # 火焰中心（黄白色）
                    blue = 0
                    green = int(230 - distance * 2)
                    red = 255
                elif distance < fire_width/2:
                    # 火焰中间（橙色）
                    blue = 0
                    green = int(180 - distance * 2)
                    red = 255
                else:
                    # 火焰边缘（红色）
                    blue = 0
                    green = int(max(0, 100 - distance * 2))
                    red = 255
                
                # 添加随机抖动
                blue = min(255, max(0, blue + np.random.randint(-10, 10)))
                green = min(255, max(0, green + np.random.randint(-10, 10)))
                red = min(255, max(0, red + np.random.randint(-5, 5)))
                
                # 设置像素颜色
                image[y, x] = (blue, green, red)
    
    # 添加烟雾效果
    smoke_center_x, smoke_center_y = fire_center_x, fire_center_y - fire_height//2 - 20
    smoke_width, smoke_height = 120, 60
    
    for y in range(smoke_center_y - smoke_height//2, smoke_center_y + smoke_height//2):
        for x in range(smoke_center_x - smoke_width//2, smoke_center_x + smoke_width//2):
            if 0 <= x < width and 0 <= y < height:
                # 烟雾中心到当前点的距离
                dx = x - smoke_center_x
                dy = y - smoke_center_y
                distance = np.sqrt(dx**2 + dy**2)
                
                # 烟雾颜色计算（灰色，透明度随距离增加而减小）
                if distance < smoke_width/2:
                    alpha = max(0, 1 - distance/(smoke_width/2)) * 0.7
                    smoke_color = 200
                    
                    # 获取当前背景颜色
                    curr_blue, curr_green, curr_red = image[y, x]
                    
                    # 混合颜色
                    blue = int(curr_blue * (1 - alpha) + smoke_color * alpha)
                    green = int(curr_green * (1 - alpha) + smoke_color * alpha)
                    red = int(curr_red * (1 - alpha) + smoke_color * alpha)
                    
                    # 设置像素颜色
                    image[y, x] = (blue, green, red)
    
    return image

def send_image_to_ai_service(image):
    """将图像发送到AI服务进行分析"""
    # 编码图像为JPEG格式
    success, encoded_image = cv2.imencode('.jpg', image)
    if not success:
        print("图像编码失败")
        return None
    
    # 创建表单数据
    files = {
        'frame': ('test_fire.jpg', encoded_image.tobytes(), 'image/jpeg')
    }
    
    data = {
        'camera_id': 'test_camera',
        'enable_face_recognition': 'false',
        'enable_object_detection': 'true',
        'enable_behavior_detection': 'false',
        'enable_fire_detection': 'true'
    }
    
    try:
        response = requests.post(AI_SERVICE_URL, files=files, data=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def draw_detection_results(image, results):
    """在图像上绘制检测结果"""
    if not results or 'detections' not in results['results']:
        return image
    
    # 复制图像以避免修改原图
    result_image = image.copy()
    
    # 绘制检测结果
    for detection in results['results']['detections']:
        if 'bbox' in detection:
            # 获取边界框坐标
            x1, y1, x2, y2 = detection['bbox']
            
            # 确定颜色
            if 'fire' in detection['type'].lower():
                color = (0, 0, 255)  # 红色
            elif 'smoke' in detection.get('detection_type', '').lower():
                color = (128, 128, 128)  # 灰色
            else:
                color = (0, 255, 0)  # 绿色
            
            # 绘制边界框
            cv2.rectangle(result_image, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            
            # 准备标签
            if 'class_name' in detection:
                label = f"{detection['class_name']} {detection['confidence']:.2f}"
            else:
                label = f"{detection['type']} {detection['confidence']:.2f}"
            
            # 绘制标签背景
            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(
                result_image, 
                (int(x1), int(y1) - text_size[1] - 5), 
                (int(x1) + text_size[0], int(y1)), 
                color, 
                -1
            )
            
            # 绘制标签
            cv2.putText(
                result_image, 
                label, 
                (int(x1), int(y1) - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (255, 255, 255), 
                2
            )
    
    return result_image

def main():
    """主函数"""
    print("创建测试火焰图像...")
    test_image = create_test_fire_image()
    
    # 保存测试图像
    cv2.imwrite("test_fire_image.jpg", test_image)
    print("测试图像已保存为 test_fire_image.jpg")
    
    print("发送图像到AI服务进行分析...")
    results = send_image_to_ai_service(test_image)
    
    if results:
        print("分析结果:")
        print(json.dumps(results, indent=2))
        
        if 'results' in results and 'detections' in results['results']:
            print(f"检测到 {len(results['results']['detections'])} 个目标")
            
            # 绘制检测结果
            result_image = draw_detection_results(test_image, results)
            cv2.imwrite("test_fire_detection_result.jpg", result_image)
            print("检测结果已保存为 test_fire_detection_result.jpg")
            
            # 显示结果图像
            cv2.imshow("火焰检测结果", result_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("未检测到任何目标")
    else:
        print("分析失败")

if __name__ == "__main__":
    main() 