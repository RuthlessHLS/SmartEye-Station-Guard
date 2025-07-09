# 文件: ai_service/core/video_stream.py
import cv2
import time
import threading
import numpy as np
from typing import List, Callable, Optional


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

        # 如果读取成功，使用 yield 将这一帧图像"生产"出去
        yield frame

    # 循环结束后（理论上对于实时流不会结束），释放资源
    cap.release()


class VideoStream:
    """
    视频流处理类，负责管理视频流的捕获和AI处理
    """
    
    def __init__(self, stream_url: str):
        """
        初始化视频流
        
        Args:
            stream_url (str): 视频流URL
        """
        self.stream_url = stream_url
        self.cap: Optional[cv2.VideoCapture] = None
        self.processors: List[Callable[[np.ndarray], None]] = []
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
    
    def add_processor(self, processor: Callable[[np.ndarray], None]):
        """
        添加帧处理器
        
        Args:
            processor: 接受frame作为参数的处理函数
        """
        with self.lock:
            self.processors.append(processor)
    
    def start(self) -> bool:
        """
        启动视频流处理
        
        Returns:
            bool: 是否成功启动
        """
        if self.is_running:
            print(f"视频流 {self.stream_url} 已在运行中")
            return True
        
        # 尝试连接视频流
        self.cap = cv2.VideoCapture(self.stream_url)
        if not self.cap.isOpened():
            print(f"错误: 无法打开视频流 {self.stream_url}")
            return False
        
        # 启动处理线程
        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
        
        print(f"成功启动视频流: {self.stream_url}")
        return True
    
    def stop(self):
        """
        停止视频流处理
        """
        self.is_running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        print(f"已停止视频流: {self.stream_url}")
    
    def _process_loop(self):
        """
        视频处理主循环
        """
        retry_count = 0
        max_retries = 5
        
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    retry_count += 1
                    print(f"视频流读取失败，重试 {retry_count}/{max_retries}")
                    
                    if retry_count >= max_retries:
                        print("达到最大重试次数，尝试重新连接...")
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.stream_url)
                        retry_count = 0
                    
                    time.sleep(1)
                    continue
                
                # 重置重试计数
                retry_count = 0
                
                # 处理帧
                with self.lock:
                    for processor in self.processors:
                        try:
                            processor(frame)
                        except Exception as e:
                            print(f"处理器执行错误: {e}")
                
                # 控制帧率，避免过度消耗CPU
                time.sleep(0.033)  # 约30fps
                
            except Exception as e:
                print(f"视频流处理循环错误: {e}")
                time.sleep(1)
    
    def get_stream_info(self) -> dict:
        """
        获取视频流信息
        
        Returns:
            dict: 包含视频流状态信息的字典
        """
        info = {
            "stream_url": self.stream_url,
            "is_running": self.is_running,
            "processors_count": len(self.processors)
        }
        
        if self.cap and self.cap.isOpened():
            info.update({
                "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": self.cap.get(cv2.CAP_PROP_FPS)
            })
        
        return info