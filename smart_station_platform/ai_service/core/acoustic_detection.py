# ai_service/core/acoustic_detection.py

import torch
import librosa
from panns_inference import AudioTagging


class AcousticEventDetector:
    def __init__(self, device=None):
        """
        初始化声音事件检测器。
        """
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device

        print(f"Acoustic Event Detector using device: {self.device}")

        # 1. 加载预训练的声音识别模型
        #    和人脸识别类似，这个库会在首次运行时自动下载并缓存模型。
        try:
            self.model = AudioTagging(checkpoint_path=None, device=self.device)
            print("Acoustic event detection model loaded successfully.")
        except Exception as e:
            self.model = None
            print(f"Failed to load acoustic event detection model: {e}")

    def detect_events(self, audio_path, top_n=5):
        """
        识别给定音频文件中的声音事件。

        Args:
            audio_path (str): 待识别音频文件的路径 (如 .wav, .mp3)。
            top_n (int): 返回置信度最高的n个结果。

        Returns:
            list: 包含每个识别到的声音事件及其置信度的列表。
        """
        if self.model is None:
            print("Acoustic model not loaded, skipping detection.")
            return []

        try:
            # 1. 使用 librosa 加载音频文件
            #    sr=32000 是模型所期望的采样率
            (audio, _) = librosa.core.load(audio_path, sr=32000, mono=True)
        except Exception as e:
            print(f"Error loading audio file {audio_path}: {e}")
            return []

        # 2. 使用模型进行推理
        #    模型输入需要是 (N,) 的numpy数组
        audio = audio[None, :]  # 增加一个批次维度 -> (1, N)
        framewise_output, clipwise_output = self.model.inference(audio)

        # clipwise_output 包含了整个片段的识别结果和置信度
        # 我们将结果格式化
        results = []
        sorted_indexes = (-clipwise_output[0]).argsort()

        for i in range(top_n):
            idx = sorted_indexes[i]
            class_name = self.model.labels[idx]
            confidence = clipwise_output[0][idx]
            results.append({
                "event": class_name,
                "confidence": round(float(confidence), 3)
            })

        return results