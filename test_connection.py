#!/usr/bin/env python3
import requests
import time

def test_connection():
    """测试服务器连接"""
    base_url = "http://localhost:8000"
    
    # 测试基本连接
    try:
        print("正在测试服务器连接...")
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ 服务器基本连接成功 - 状态码: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ 服务器连接失败 - 连接被拒绝")
        return False
    except requests.exceptions.Timeout:
        print("❌ 服务器连接超时")
        return False
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def test_api_endpoints():
    """测试特定的API端点"""
    base_url = "http://localhost:8000"
    endpoints = [
        "/api/alerts/ai-results/",
        "/api/alerts/list/",
        "/swagger/",
        "/admin/"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"✅ {endpoint} - 状态码: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ {endpoint} - 连接被拒绝")
        except Exception as e:
            print(f"❌ {endpoint} - 错误: {e}")

if __name__ == "__main__":
    print("=== Django服务器连接测试 ===")
    
    # 给服务器一些启动时间
    print("等待服务器启动...")
    time.sleep(5)
    
    if test_connection():
        print("\n=== API端点测试 ===")
        test_api_endpoints()
    else:
        print("服务器未启动，请检查后台进程") 