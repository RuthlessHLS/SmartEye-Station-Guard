import os
import requests
import torch
from ultralytics import YOLO

# 定义模型保存路径
MODEL_DIR = "D:/G_/ai_assets/models/torch"
os.makedirs(MODEL_DIR, exist_ok=True)

def download_fire_model():
    """下载火焰检测YOLOv8预训练模型"""
    print("开始下载火焰检测模型...")
    
    # 方法1：使用YOLO直接加载预训练模型（会自动下载）
    model_path = os.path.join(MODEL_DIR, "yolov8n-fire.pt")
    
    # 检查模型是否已存在
    if os.path.exists(model_path):
        print(f"火焰检测模型已存在: {model_path}")
        return model_path
    
    # 如果模型不存在，从预训练的火焰检测模型加载
    try:
        print("从Ultralytics Hub下载YOLOv8火焰检测模型...")
        # 这将自动下载并保存预训练的火焰检测模型
        model = YOLO("keremberke/yolov8n-fire-detection")
        
        # 保存模型到本地
        model.export(format="pt")
        
        # 移动导出的模型到目标位置
        os.rename("yolov8n-fire_openvino_model", model_path)
        
        print(f"火焰检测模型已下载并保存到: {model_path}")
        return model_path
    except Exception as e:
        print(f"自动下载失败: {e}")
        
        # 方法2：手动下载模型
        print("尝试手动下载模型...")
        model_url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
        
        response = requests.get(model_url, stream=True)
        if response.status_code == 200:
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"基础YOLOv8模型已下载到: {model_path}")
            print("请注意：这是通用模型，不是专门的火焰检测模型")
            return model_path
        else:
            print(f"下载失败，状态码: {response.status_code}")
            return None

if __name__ == "__main__":
    model_path = download_fire_model()
    if model_path:
        print(f"模型下载完成: {model_path}")
        # 加载模型验证
        model = YOLO(model_path)
        print(f"模型加载成功，类别: {model.names}")
    else:
        print("模型下载失败") 