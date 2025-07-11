import cv2
import time
import subprocess
import sys
import argparse
import numpy as np
from pathlib import Path

def create_test_frame(width=640, height=480, frame_count=0):
    """生成测试视频帧"""
    # 创建彩色条纹背景
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    stripe_width = width // 7
    colors = [
        (255, 0, 0),   # 红
        (255, 255, 0), # 黄
        (0, 255, 0),   # 绿
        (0, 255, 255), # 青
        (0, 0, 255),   # 蓝
        (255, 0, 255), # 紫
        (255, 255, 255)# 白
    ]
    
    for i, color in enumerate(colors):
        frame[:, i*stripe_width:(i+1)*stripe_width] = color
        
    # 添加帧计数器
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = f'Frame: {frame_count}'
    cv2.putText(frame, text, (50, 50), font, 1, (0, 0, 0), 2)
    
    return frame

def stream_to_rtmp(rtmp_url="rtmp://localhost:1935/live/webcam", camera_id=0, test_mode=False, width=640, height=480, fps=30):
    """推流到RTMP服务器"""
    
    if test_mode:
        print(f"使用测试模式，生成{width}x{height}的测试画面")
        frame = create_test_frame(width, height)
    else:
        print(f"尝试打开摄像头 {camera_id}")
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"错误：无法打开摄像头 {camera_id}")
            return
        ret, frame = cap.read()
        if not ret:
            print("错误：无法读取视频帧")
            return
        
    # 构建FFmpeg命令
    command = [
        'ffmpeg',
        '-y',  # 覆盖输出文件
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f"{width}x{height}",
        '-r', str(fps),
        '-i', '-',  # 从管道读取输入
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        '-f', 'flv',
        '-flvflags', 'no_duration_filesize',
        '-loglevel', 'warning',  # 只显示警告和错误
        rtmp_url
    ]
    
    try:
        # 启动FFmpeg进程
        print(f"开始推流到 {rtmp_url}")
        print("FFmpeg命令:", ' '.join(command))
        ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE)
        
        frame_count = 0
        start_time = time.time()
        
        print("按 Ctrl+C 停止推流")
        while True:
            if test_mode:
                frame = create_test_frame(width, height, frame_count)
            else:
                ret, frame = cap.read()
                if not ret:
                    print("错误：无法读取视频帧")
                    break
            
            # 写入视频帧
            try:
                ffmpeg.stdin.write(frame.tobytes())
            except BrokenPipeError:
                print("错误：FFmpeg进程已终止")
                break
            except IOError as e:
                print(f"IO错误：{e}")
                break
                
            frame_count += 1
            if frame_count % fps == 0:  # 每秒显示一次状态
                elapsed_time = time.time() - start_time
                current_fps = frame_count / elapsed_time
                print(f"已推流 {frame_count} 帧，当前帧率：{current_fps:.2f} fps")
            
            # 控制帧率
            time.sleep(1/fps)
            
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，正在停止推流...")
    finally:
        if not test_mode:
            cap.release()
        if ffmpeg:
            try:
                ffmpeg.stdin.close()
                ffmpeg.wait(timeout=5)
            except:
                ffmpeg.kill()
        print("推流已停止")

def main():
    parser = argparse.ArgumentParser(description='推流到RTMP服务器')
    parser.add_argument('--url', default="rtmp://localhost:1935/live/webcam", help='RTMP服务器地址')
    parser.add_argument('--camera', type=int, default=0, help='摄像头设备ID')
    parser.add_argument('--test', action='store_true', help='使用测试画面代替摄像头')
    parser.add_argument('--width', type=int, default=640, help='视频宽度')
    parser.add_argument('--height', type=int, default=480, help='视频高度')
    parser.add_argument('--fps', type=int, default=30, help='视频帧率')
    
    args = parser.parse_args()
    
    stream_to_rtmp(
        rtmp_url=args.url,
        camera_id=args.camera,
        test_mode=args.test,
        width=args.width,
        height=args.height,
        fps=args.fps
    )

if __name__ == '__main__':
    main() 