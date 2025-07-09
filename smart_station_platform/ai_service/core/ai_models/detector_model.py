# 文件: ai_service/core/ai_models/detector_model.py
# 描述: 定义一个标准的PyTorch目标检测模型结构。

import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

def get_model(num_classes):
    """
    加载一个预训练的Faster R-CNN模型，并根据类别数量修改其分类头。

    Args:
        num_classes (int): 数据集中的类别总数 (例如: COCO是90类 + 1个背景 = 91)。

    Returns:
        torch.nn.Module: 一个可用于训练或推理的PyTorch模型。
    """
    # 1. 加载一个在COCO数据集上预训练过的模型
    #    pretrained=True 会下载模型权重，如果本地没有的话
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights='DEFAULT')

    # 2. 获取分类器的输入特征数
    in_features = model.roi_heads.box_predictor.cls_score.in_features

    # 3. 将预训练的头部替换为一个新的头部
    #    新的头部将具有适合我们自己数据集的、正确数量的输出类别
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    return model