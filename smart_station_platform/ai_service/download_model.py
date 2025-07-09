# download_model.py
import torch
import torchvision.models.detection as detection
import os

print("开始下载 PyTorch Vision 官方预训练模型...")
print("这可能需要几分钟，请耐心等待...")

# 1. 加载官方预训练的Faster R-CNN模型
#    这会自动从网上下载模型权重
model = detection.fasterrcnn_resnet50_fpn_v2(weights='FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT')

# 2. 指定我们项目中约定的模型文件名
output_filename = "weights/object_detection_best.pth"

# 3. 保存模型的“状态字典”(state_dict)，也就是它的权重
torch.save(model.state_dict(), output_filename)

print("-" * 50)
print(f"模型下载并保存成功！")
print(f"文件名: {output_filename}")
print(f"文件大小: {os.path.getsize(output_filename) / 1024 / 1024:.2f} MB")
print("请手动将此文件移动到 'ai_service/weights/' 目录下。")
print("-" * 50)