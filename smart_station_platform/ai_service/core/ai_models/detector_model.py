# ai_service/core/ai_models/detector_model.py
import torch.nn as nn
from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2

def get_model(num_classes):
    """
    获取一个Faster R-CNN模型结构。
    这个模型结构将用于加载在COCO数据集上预训练的权重。
    """
    # 我们直接返回一个带有91个输出类别（COCO数据集的类别数）的模型结构
    # 注意，这里的num_classes参数实际上是为了匹配COCO模型，我们会在app.py中硬编码为91
    model = fasterrcnn_resnet50_fpn_v2(num_classes=num_classes)
    return model