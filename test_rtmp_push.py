#!/usr/bin/env python3
"""
测试RTMP推流脚本
用于向nginx RTMP服务器推送测试视频流
"""

import cv2
import subprocess
import sys
import time
import numpy as np
from datetime import datetime
import threading
import os

def create_test_video_frame(frame_count, width=640, height=480):
    """创建测试视频帧"""
    # 创建背景
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 添加渐变背景
    for y in range(height):
        for x in range(width):
            frame[y, x] = [
                int(255 * x / width),
                int(255 * y / height), 
                int(255 * (x + y) / (width + height))
            ]
    
    # 添加时间信息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"Test Stream", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, timestamp, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Frame: {frame_count}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # 添加移动的方块
    box_x = int((frame_count * 2) % (width - 50))
    box_y = int(height // 2 + 50 * np.sin(frame_count * 0.1))
    cv2.rectangle(frame, (box_x, box_y), (box_x + 50, box_y + 50), (0, 255, 255), -1)
    
    return frame

def push_test_stream_ffmpeg(rtmp_url="rtmp://localhost:1935/live/test", duration=60):
    """使用FFmpeg推送测试流"""
    print(f"🚀 开始推送测试流到: {rtmp_url}")
    print(f"⏱️  推流时长: {duration}秒")
    
    try:
        # FFmpeg命令：生成测试视频并推流
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'testsrc2=size=640x480:rate=25',  # 生成测试视频
            '-f', 'lavfi', 
            '-i', 'sine=frequency=1000:sample_rate=44100',  # 生成测试音频
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-g', '50',
            '-keyint_min', '25',
            '-sc_threshold', '0',
            '-f', 'flv',
            '-t', str(duration),
            rtmp_url
        ]
        
        print("🔧 FFmpeg命令:", ' '.join(cmd))
        
        # 启动FFmpeg进程
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        print("✅ FFmpeg进程已启动")
        print("📺 您现在可以在浏览器中测试以下地址:")
        print(f"   RTMP: {rtmp_url}")
        print(f"   HLS:  http://localhost:8080/hls/test.m3u8")
        print(f"   FLV:  http://localhost:8080/live/test.flv")
        print()
        print("⏹️  按 Ctrl+C 停止推流")
        
        # 等待进程完成或用户中断
        try:
            stdout, stderr = process.communicate(timeout=duration + 10)
            if process.returncode == 0:
                print("✅ 推流完成")
            else:
                print(f"❌ 推流失败，返回码: {process.returncode}")
                if stderr:
                    print("错误信息:", stderr)
        except subprocess.TimeoutExpired:
            print("⏱️  推流超时")
            process.kill()
        except KeyboardInterrupt:
            print("\n🛑 用户中断，正在停止推流...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            print("✅ 推流已停止")
            
    except FileNotFoundError:
        print("❌ 错误：未找到 FFmpeg")
        print("💡 请确保已安装 FFmpeg 并添加到系统 PATH")
        print("   下载地址: https://ffmpeg.org/download.html")
        return False
    except Exception as e:
        print(f"❌ 推流失败: {e}")
        return False
    
    return True

def push_test_stream_opencv(rtmp_url="rtmp://localhost:1935/live/test", duration=60):
    """使用OpenCV推送测试流（备选方案）"""
    print(f"🚀 使用OpenCV推送测试流到: {rtmp_url}")
    
    try:
        # 尝试使用cv2.VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        out = cv2.VideoWriter(rtmp_url, fourcc, 25.0, (640, 480))
        
        if not out.isOpened():
            raise Exception("无法打开RTMP流")
        
        frame_count = 0
        start_time = time.time()
        
        print("✅ OpenCV推流已启动")
        print("⏹️  按 Ctrl+C 停止推流")
        
        while time.time() - start_time < duration:
            frame = create_test_video_frame(frame_count)
            out.write(frame)
            frame_count += 1
            time.sleep(1/25)  # 25 FPS
            
            if frame_count % 250 == 0:  # 每10秒打印一次状态
                elapsed = time.time() - start_time
                print(f"📈 已推流 {elapsed:.1f}秒, 帧数: {frame_count}")
        
        out.release()
        print("✅ OpenCV推流完成")
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断，正在停止推流...")
        if 'out' in locals():
            out.release()
        print("✅ 推流已停止")
        return True
    except Exception as e:
        print(f"❌ OpenCV推流失败: {e}")
        return False

def check_nginx_status():
    """检查nginx RTMP服务器状态"""
    try:
        import requests
        response = requests.get("http://localhost:8080/stat", timeout=5)
        if response.status_code == 200:
            print("✅ nginx RTMP服务器运行正常")
            return True
    except:
        pass
    
    print("❌ nginx RTMP服务器未响应")
    print("💡 请确保nginx RTMP服务器已启动:")
    print("   - 运行 start_services.bat")
    print("   - 或者手动启动 nginx.exe")
    return False

def main():
    print("🎬 RTMP测试推流工具")
    print("=" * 50)
    
    # 检查nginx服务器
    if not check_nginx_status():
        return
    
    # 选择推流方式
    print("\n🔧 请选择推流方式:")
    print("1. FFmpeg推流 (推荐)")
    print("2. OpenCV推流 (备选)")
    print("3. 退出")
    
    choice = input("\n请输入选择 (1-3): ").strip()
    
    if choice == "1":
        success = push_test_stream_ffmpeg()
    elif choice == "2":
        success = push_test_stream_opencv()
    elif choice == "3":
        print("👋 退出")
        return
    else:
        print("❌ 无效选择")
        return
    
    if success:
        print("\n🎉 推流测试完成！")
        print("💡 您现在可以在前端测试视频播放功能")

if __name__ == "__main__":
    main() 