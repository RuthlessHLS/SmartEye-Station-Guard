# 文件: ai_service/core/ai_models/detector_model.py
# 描述: 定义一个标准的PyTorch目标检测模型结构，主要用于Faster R-CNN。
#       在当前架构中，通用目标检测器(object_detection.py)默认使用YOLOv8，
#       此文件可作为Faster R-CNN的备用或历史模型定义。

import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import torch.nn as nn  # 用于更清晰的类型提示和可能的基础模块
import logging

logger = logging.getLogger(__name__)


def get_model(num_classes: int, use_pretrained_weights: bool = True) -> nn.Module:
    """
    加载一个预训练的Faster R-CNN模型，并根据类别数量修改其分类头。

    Args:
        num_classes (int): 数据集中的类别总数 (例如: COCO是90类 + 1个背景 = 91)。
        use_pretrained_weights (bool): 是否使用在COCO数据集上预训练过的权重。
                                        设为True会下载模型权重（如果本地没有的话）。
    Returns:
        torch.nn.Module: 一个可用于训练或推理的PyTorch模型。
    """
    logger.info(f"正在加载 Faster R-CNN ResNet50 FPN 模型 (num_classes={num_classes})")

    # 1. 加载一个在COCO数据集上预训练过的模型
    #    weights='DEFAULT' 会自动从网上下载模型权重，如果本地没有的话
    try:
        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
            weights='FasterRCNN_ResNet50_FPN_Weights.DEFAULT' if use_pretrained_weights else None
        )
        if use_pretrained_weights:
            logger.info("已加载 Faster R-CNN 模型的预训练权重。")
        else:
            logger.info("正在加载 Faster R-CNN 模型结构，不使用预训练权重。")
    except Exception as e:
        logger.error(f"加载 Faster R-CNN 基础模型失败: {e}", exc_info=True)
        raise RuntimeError(f"无法初始化 Faster R-CNN 模型: {e}")

    # 2. 获取分类器的输入特征数
    try:
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        logger.debug(f"Faster R-CNN 分类器输入特征数: {in_features}")
    except AttributeError as e:
        logger.error(f"无法获取 Faster R-CNN 分类器的输入特征数: {e}", exc_info=True)
        raise RuntimeError(f"模型结构异常，无法找到分类器输入特征: {e}")

    # 3. 将预训练的头部替换为一个新的头部
    #    新的头部将具有适合我们自己数据集的、正确数量的输出类别
    try:
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
        logger.info(f"Faster R-CNN 模型分类头已修改为 {num_classes} 个类别。")
    except Exception as e:
        logger.error(f"修改 Faster R-CNN 分类头失败: {e}", exc_info=True)
        raise RuntimeError(f"无法修改 Faster R-CNN 分类器: {e}")

    return model


if __name__ == '__main__':
    # 示例用法：加载一个用于2个类别（例如：person, background）的模型
    try:
        # COCO数据集有80个对象类别，加上背景总共81个，如果用于自定义数据集，
        # num_classes 应为自定义类别数 + 1 (背景)
        sample_num_classes = 2  # 例如：1个前景类别 + 1个背景类别
        test_model = get_model(sample_num_classes)
        logger.info(f"测试模型 {test_model.__class__.__name__} 加载成功！")
        logger.info(f"模型预测器输出类别数: {test_model.roi_heads.box_predictor.cls_score.out_features}")

        # 简单测试一下模型
        import torch

        # 创建一个随机输入图像张量 (Batch_size, Channels, Height, Width)
        dummy_input = torch.randn(1, 3, 800, 800)
        # 将模型设置为评估模式
        test_model.eval()
        # 运行推理
        with torch.no_grad():
            output = test_model(dummy_input)
        logger.info(f"模型测试推理完成。输出类型: {type(output)}, 输出数量: {len(output)}")
        logger.info(f"第一个输出字典的键: {output[0].keys()}")

    except RuntimeError as e:
        logger.error(f"模型加载或测试失败: {e}")
    except Exception as e:
        logger.error(f"发生未知错误: {e}", exc_info=True)