import os
import requests
from tqdm import tqdm

def download_file(url, save_path):
    """
    下载文件并显示进度条
    """
    # 创建保存目录（如果不存在）
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # 发送GET请求
    response = requests.get(url, stream=True)
    # 获取文件大小
    total_size = int(response.headers.get('content-length', 0))
    
    # 打开文件并写入
    with open(save_path, 'wb') as file, tqdm(
        desc=os.path.basename(save_path),
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            progress_bar.update(size)

def main():
    # YOLOv8n模型下载链接
    model_url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    # 保存路径
    save_path = "G:/ai_assets/models/torch/yolov8n.pt"
    
    print(f"开始下载YOLOv8n模型到: {save_path}")
    try:
        download_file(model_url, save_path)
        print("✅ 下载完成！")
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        # 尝试备用链接
        backup_url = "https://huggingface.co/Bingsu/adetailer/resolve/main/weights/yolov8n.pt"
        print(f"尝试使用备用链接下载...")
        try:
            download_file(backup_url, save_path)
            print("✅ 使用备用链接下载成功！")
        except Exception as e:
            print(f"❌ 备用链接下载也失败了: {e}")

if __name__ == "__main__":
    main() 