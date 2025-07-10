"""
火焰检测测试脚本
用于测试智能站点守护中的火焰检测功能

用法:
    python test_fire_detection.py --image <图像路径> [--save] [--show]
    python test_fire_detection.py --video <视频路径> [--save] [--show]
    
选项:
    --image       图像文件路径
    --video       视频文件路径
    --save        保存带有检测结果的图像/视频
    --show        显示检测结果
"""

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

def test_fire_detection(image_path):
    """测试火焰检测功能"""
    print(f"正在测试火焰检测功能，使用图像: {image_path}")
    
    # 检查图像文件是否存在
    if not os.path.exists(image_path):
        print(f"错误: 图像文件 '{image_path}' 不存在")
        return False
    
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
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
    
    # 测试检测性能
    start_time = time.time()
    detections = fire_detector.detect(image, confidence_threshold=0.3)  # 降低置信度阈值以捕获更多可能的火焰
    elapsed_time = time.time() - start_time
    
    # 绘制检测结果
    output_image, _ = fire_detector.process_video_frame(image, confidence_threshold=0.3, draw_result=True)
    
    # 打印检测结果
    print(f"检测完成，耗时 {elapsed_time:.3f} 秒")
    print(f"检测到 {len(detections)} 个火焰/烟雾对象:")
    
    for i, det in enumerate(detections):
        print(f"  {i+1}. 类型: {det['type']}, 类别: {det['class_name']}, 置信度: {det['confidence']:.3f}")
        print(f"     坐标: {det['coordinates']}")
    
    # 显示图像
    cv2.imshow("Fire Detection Result", output_image)
    print("按任意键关闭窗口...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 使用命令行参数提供的图像路径
        image_path = sys.argv[1]
    else:
        # 默认使用示例图像
        image_path = input("请输入火焰图像的路径: ")
    
    test_fire_detection(image_path) 