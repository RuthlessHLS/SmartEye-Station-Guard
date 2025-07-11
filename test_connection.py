#!/usr/bin/env python3
import os
import sys
import requests
import socket
import time

def test_internet_connection():
    """测试互联网连接"""
    hosts = ["www.baidu.com", "github.com", "www.google.com"]
    
    print("测试互联网连接...")
    for host in hosts:
        try:
            # 尝试解析域名
            print(f"尝试解析 {host}...")
            ip = socket.gethostbyname(host)
            print(f"  成功: {host} -> {ip}")
        except Exception as e:
            print(f"  失败: {host} - {e}")
    
    print("\n测试HTTP请求...")
    urls = [
        "https://www.baidu.com", 
        "https://github.com",
        "https://raw.githubusercontent.com/simon-zerisenay/FireGuardVision/main/fire.pt"
    ]
    
    for url in urls:
        try:
            print(f"尝试请求 {url}...")
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            print(f"  成功: 状态码 {response.status_code}, 耗时 {elapsed:.2f}秒")
        except Exception as e:
            print(f"  失败: {url} - {e}")
    
    print("\n环境变量信息:")
    proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]
    for var in proxy_vars:
        value = os.environ.get(var)
        print(f"  {var}: {value if value else '未设置'}")
    
    # 检查pip配置
    print("\n尝试使用pip安装小型包...")
    try:
        import subprocess
        result = subprocess.run(["pip", "install", "six", "--upgrade"], 
                               capture_output=True, text=True)
        print(f"pip安装结果: {'成功' if result.returncode == 0 else '失败'}")
        if result.returncode != 0:
            print(f"错误信息: {result.stderr}")
    except Exception as e:
        print(f"pip测试失败: {e}")

if __name__ == "__main__":
    test_internet_connection() 