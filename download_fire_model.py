import os
import requests

# 定义模型保存路径
MODEL_DIR = "D:/G_/ai_assets/models/torch"
os.makedirs(MODEL_DIR, exist_ok=True)

def download_fire_model():
    """下载火焰检测YOLOv8预训练模型"""
    print("开始下载火焰检测模型...")
    
    # 模型路径
    model_path = os.path.join(MODEL_DIR, "yolov8n-fire.pt")
    
    # 检查模型是否已存在
    if os.path.exists(model_path):
        print(f"火焰检测模型已存在: {model_path}")
        return model_path
    
    # 尝试直接从GitHub下载预训练的火焰检测模型
    try:
        print("从GitHub下载专用火焰检测模型...")
        # 这个URL指向FireGuardVision仓库的火焰检测模型
        model_url = "https://github.com/simon-zerisenay/FireGuardVision/raw/main/fire.pt"
        
        response = requests.get(model_url, stream=True)
        if response.status_code == 200:
            with open(model_path, 'wb') as f:
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024  # 1 KB
                downloaded = 0
                
                print("开始下载模型文件...")
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 计算下载进度
                        if total_size > 0:
                            percent = int(100 * downloaded / total_size)
                            if percent % 10 == 0:  # 每10%更新一次
                                print(f"下载进度: {percent}%")
            
            print(f"专用火焰检测模型已下载到: {model_path}")
            return model_path
        else:
            print(f"从GitHub下载模型失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"从GitHub下载失败: {e}")
    
    # 回退选项：如果专用模型下载失败，尝试下载通用YOLO模型
    print("尝试下载通用YOLOv8模型作为备选...")
    model_url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    
    try:
        response = requests.get(model_url, stream=True)
        if response.status_code == 200:
            with open(model_path, 'wb') as f:
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024  # 1 KB
                downloaded = 0
                
                print("开始下载通用模型文件...")
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 计算下载进度
                        if total_size > 0:
                            percent = int(100 * downloaded / total_size)
                            if percent % 10 == 0:  # 每10%更新一次
                                print(f"下载进度: {percent}%")
            
            print(f"通用YOLOv8模型已下载到: {model_path}")
            print("请注意：这是通用模型，不是专门的火焰检测模型")
            return model_path
        else:
            print(f"下载通用模型失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        print(f"下载通用模型失败: {e}")
        return None

if __name__ == "__main__":
    model_path = download_fire_model()
    if model_path:
        print(f"模型下载完成: {model_path}")
        print("请使用fire_detection_enhance.py脚本或test_fire_detection.py进行测试")
    else:
        print("模型下载失败")