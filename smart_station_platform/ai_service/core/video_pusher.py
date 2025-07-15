 
import subprocess
import numpy as np
import logging
import threading

logger = logging.getLogger(__name__)

class VideoPusher:
    """
    使用 FFmpeg 将视频帧推送到 RTMP 服务器的类。
    """
    def __init__(self, output_url: str, width: int, height: int, fps: int = 25):
        """
        初始化 VideoPusher。

        Args:
            output_url (str): 要推送到的 RTMP 流地址 (例如, "rtmp://localhost/live/processed").
            width (int): 视频帧的宽度。
            height (int): 视频帧的高度。
            fps (int): 视频的帧率。
        """
        self.output_url = output_url
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None
        self._is_running = False

    def start(self):
        """
        启动 FFmpeg 进程以开始接收帧并推送到 RTMP 服务器。
        """
        if self.process and self.process.poll() is None:
            logger.warning("FFmpeg process is already running.")
            return

        command = [
            'ffmpeg',
            '-y',  # 无需确认即可覆盖输出文件
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',  # OpenCV 默认的颜色格式
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', '-',  # 从标准输入读取
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', # H.264 编码常用的像素格式
            '-preset', 'ultrafast',  # 优先考虑速度以减少延迟
            '-tune', 'zerolatency', # 针对低延迟进行优化
            '-f', 'flv',  # RTMP 使用的封装格式
            self.output_url
        ]
        
        try:
            # 使用 DEVNULL 来忽略 ffmpeg 的标准输出，但将 stderr 传递给管道以便调试
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self._is_running = True
            logger.info(f"FFmpeg process started for {self.output_url}. PID: {self.process.pid}")

            # 在单独的线程中读取 stderr 以防止管道阻塞
            threading.Thread(target=self._log_stderr, daemon=True).start()

        except FileNotFoundError:
            logger.error("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")
            raise
        except Exception as e:
            logger.error(f"Failed to start FFmpeg process: {e}")
            raise

    def _log_stderr(self):
        """持续读取并记录 FFmpeg 的 stderr 输出。"""
        if not self.process or not self.process.stderr:
            return
        for line in iter(self.process.stderr.readline, b''):
            logger.debug(f"ffmpeg_stderr: {line.decode('utf-8').strip()}")
        logger.info("FFmpeg stderr stream closed.")


    def push_frame(self, frame: np.ndarray):
        """
        将单个视频帧写入 FFmpeg 进程。

        Args:
            frame (np.ndarray): 要推送的视频帧 (BGR 格式)。
        """
        if not self.process or self.process.poll() is not None:
            if self._is_running: # 只在之前是运行时才记录错误
                 logger.error("FFmpeg process is not running. Cannot push frame.")
            self._is_running = False
            return
        
        try:
            self.process.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError) as e:
            logger.error(f"Error writing frame to FFmpeg: {e}. The process might have terminated.")
            self._is_running = False
            # 在这里可以添加重新启动 FFmpeg 的逻辑
            self.close()

    def close(self):
        """
        干净地关闭 FFmpeg 进程。
        """
        self._is_running = False
        if self.process and self.process.poll() is None:
            logger.info(f"Closing FFmpeg process for {self.output_url}...")
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.wait(timeout=5)
                logger.info(f"FFmpeg process (PID: {self.process.pid}) closed successfully.")
            except subprocess.TimeoutExpired:
                logger.warning(f"FFmpeg process (PID: {self.process.pid}) did not terminate gracefully. Forcing kill.")
                self.process.kill()
            except Exception as e:
                logger.error(f"Exception while closing FFmpeg process: {e}")
                self.process.kill() # 确保进程被终止
        self.process = None

    def is_running(self) -> bool:
        """
        检查 FFmpeg 进程是否仍在运行。
        """
        return self._is_running and self.process is not None and self.process.poll() is None 