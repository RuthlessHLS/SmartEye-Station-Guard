# 文件: smart_station_platform/ai_service/core/anti_spoofing_predictor.py
# 描述: 封装了用于检测人脸欺骗攻击的深度学习模型。

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from collections import OrderedDict


# --- 模型架构定义 (MiniFASNetV1) ---
# 这个架构与我们使用的 `4_0_0_80x80_MiniFASNetV1.pth` 模型权重完全匹配。

class Conv_block(nn.Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super(Conv_block, self).__init__()
        self.conv = nn.Conv2d(in_c, out_channels=out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_c)
        self.prelu = nn.PReLU(out_c)
    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.prelu(x)
        return x

class Linear_block(nn.Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super(Linear_block, self).__init__()
        self.conv = nn.Conv2d(in_c, out_channels=out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_c)
    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        return x

class Depth_Wise(nn.Module):
     def __init__(self, in_c, out_c, residual = False, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=1):
        super(Depth_Wise, self).__init__()
        self.conv = Conv_block(in_c, out_c=groups, kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.conv_dw = Conv_block(groups, groups, groups=groups, kernel=kernel, padding=padding, stride=stride)
        self.project = Linear_block(groups, out_c, kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.residual = residual
     def forward(self, x):
        if self.residual:
            short_cut = x
        x = self.conv(x)
        x = self.conv_dw(x)
        x = self.project(x)
        if self.residual:
            output = short_cut + x
        else:
            output = x
        return output

class Residual(nn.Module):
    def __init__(self, c, num_block, groups, kernel=(3, 3), stride=(1, 1), padding=(1, 1)):
        super(Residual, self).__init__()
        modules = []
        for _ in range(num_block):
            modules.append(Depth_Wise(c, c, residual=True, kernel=kernel, padding=padding, stride=stride, groups=groups))
        self.model = nn.Sequential(*modules)
    def forward(self, x):
        return self.model(x)

class MiniFASNet(nn.Module):
    def __init__(self, embedding_size=128, conv6_kernel=(5, 5), num_classes=3, img_channel=3):
        super(MiniFASNet, self).__init__()
        self.conv1 = Conv_block(img_channel, 32, kernel=(3, 3), stride=(2, 2), padding=(1, 1))
        self.conv2_dw = Conv_block(32, 32, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=32)
        self.conv_23 = Depth_Wise(32, 64, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=103)
        self.conv_3 = nn.Sequential(
            Depth_Wise(64, 64, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=13),
            Depth_Wise(64, 64, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=13),
            Depth_Wise(64, 64, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=13),
            Depth_Wise(64, 64, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=13),
        )
        self.conv_34 = Depth_Wise(64, 128, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=231)
        self.conv_4 = nn.Sequential(
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=231),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=52),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=26),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=77),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=26),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=26),
        )
        self.conv_45 = Depth_Wise(128, 128, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=308)
        self.conv_5 = nn.Sequential(
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=26),
            Depth_Wise(128, 128, residual=True, kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=26),
        )
        self.conv_6_sep = Conv_block(128, 512, kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.conv_6_dw = Linear_block(512, 512, groups=512, kernel=conv6_kernel, stride=(1, 1), padding=(0, 0))
        self.conv_6_flatten = nn.Flatten()
        self.linear = nn.Linear(512, embedding_size, bias=False)
        self.bn = nn.BatchNorm1d(embedding_size)
        self.drop = nn.Dropout(p=0)
        self.prob = nn.Linear(embedding_size, num_classes, bias=False)

    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2_dw(out)
        out = self.conv_23(out)
        out = self.conv_3(out)
        out = self.conv_34(out)
        out = self.conv_4(out)
        out = self.conv_45(out)
        out = self.conv_5(out)
        out = self.conv_6_sep(out)
        out = self.conv_6_dw(out)
        out = self.conv_6_flatten(out)
        out = self.linear(out)
        out = self.bn(out)
        out = self.drop(out)
        out = self.prob(out)
        return out


class AntiSpoofingPredictor:
    """
    使用轻量级深度学习模型来检测人脸欺骗攻击 (如AI换脸、视频翻拍)。
    """

    def __init__(self, model_path, device='cpu'):
        self.device = torch.device(device)
        self.model = self._load_model(model_path)
        self.model.eval()

    def _load_model(self, model_path):
        """加载预训练的PyTorch模型。"""
        # 定义与 '4_0_0_80x80_MiniFASNetV1.pth' 权重文件匹配的模型结构
        model = MiniFASNet(embedding_size=128, conv6_kernel=(5, 5), num_classes=3)

        # 加载模型权重
        state_dict = torch.load(model_path, map_location=self.device)

        # 【最终修复】处理在多GPU上训练并保存的模型(权重名称会多一个'module.'前缀)
        # 并且，修复由于模型定义差异导致的层名称不匹配问题 ('conv_3.model.0' vs 'conv_3.0')
        new_state_dict = OrderedDict()
        for k, v in state_dict.items():
            name = k[7:] if k.startswith('module.') else k
            name = name.replace('.model.', '.')  # <--- 核心修复
            new_state_dict[name] = v

        model.load_state_dict(new_state_dict)
        model = model.to(self.device)
        return model

    def predict(self, face_crop: np.ndarray) -> (bool, float):
        """
        对裁切出的人脸图像进行活体检测。

        Args:
            face_crop (np.ndarray): BGR格式的人脸图像。

        Returns:
            tuple[bool, float]: (是否是真人, 是真人的置信度)
        """
        if face_crop is None or face_crop.size == 0:
            return False, 0.0

        # 1. 预处理图像
        img = cv2.resize(face_crop, (80, 80))
        img = (img - 127.5) / 128.0  # 归一化到 [-1, 1]
        img = img.transpose((2, 0, 1))  # HWC to CHW

        # 转换为Tensor
        tensor = torch.from_numpy(img).float().unsqueeze(0).to(self.device)

        # 2. 模型推理
        with torch.no_grad():
            output = self.model(tensor)
            probabilities = F.softmax(output, dim=1).squeeze()

            # 模型输出: 0 -> fake, 1 -> real (some models have different order)
            # For 4_0_0_80x80_MiniFASNetV1 model, the output is [real, fake, spoof_type]
            # but we will only use real vs fake. index 0 is real.
            real_confidence = probabilities[0].item()

        # 3. 判断结果 (设置一个阈值)
        is_real = real_confidence > 0.8

        return is_real, real_confidence