# 文件: ai_service/core/video_stream.py
import cv2
import time


def process_video_stream(video_url: str):
    """
    连接到视频流并逐帧产生图像。
    这是一个生成器函数，可以被循环调用。
    """
    cap = cv2.VideoCapture(video_url)
    if not cap.isOpened():
        print(f"错误: 无法打开视频流 {video_url}")
        return  # 如果打不开，就结束

    print(f"成功连接到视频流: {video_url}")
    while True:
        ret, frame = cap.read()
        # 如果读取失败 (ret is False)
        if not ret:
            print("视频流结束或发生错误，5秒后尝试重连...")
            time.sleep(5)
            cap.release()  # 释放旧的连接
            cap = cv2.VideoCapture(video_url)  # 尝试重新连接
            continue  # 继续下一次循环

        # 如果读取成功，使用 yield 将这一帧图像“生产”出去
        yield frame

    # 循环结束后（理论上对于实时流不会结束），释放资源
    cap.release()