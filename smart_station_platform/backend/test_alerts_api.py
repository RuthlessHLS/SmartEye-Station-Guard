#!/usr/bin/env python3
"""
快速测试告警管理API的脚本
"""

import requests
import json
import time
from datetime import datetime

# 服务器基础URL
BASE_URL = "http://localhost:8000"

def print_response(response, title):
    """打印响应结果"""
    print(f"\n🔍 {title}")
    print(f"状态码: {response.status_code}")
    if response.headers.get('content-type', '').startswith('application/json'):
        try:
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"响应: {response.text}")
    else:
        print(f"响应: {response.text}")
    print("-" * 50)

def test_server_status():
    """测试服务器状态"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ 服务器运行正常 - 状态码: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ 服务器连接失败: {e}")
        return False

def test_swagger_docs():
    """测试Swagger文档"""
    try:
        response = requests.get(f"{BASE_URL}/swagger/", timeout=5)
        print(f"✅ Swagger文档可访问 - 状态码: {response.status_code}")
        print(f"📖 Swagger文档地址: {BASE_URL}/swagger/")
        return True
    except Exception as e:
        print(f"❌ Swagger文档访问失败: {e}")
        return False

def test_ai_results_api():
    """测试AI告警接收接口"""
    print("\n🤖 测试AI告警接收接口")
    
    # 测试数据
    test_data = {
        "camera_id": "test_camera_001",
        "event_type": "stranger_intrusion",
        "timestamp": datetime.now().isoformat(),
        "location": {"zone": "entrance", "coordinates": [100, 200]},
        "confidence": 0.95,
        "image_snapshot_url": "http://example.com/test_image.jpg",
        "video_clip_url": "http://example.com/test_video.mp4"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/alerts/ai-results/",
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        print_response(response, "AI告警接收接口测试")
        return response.status_code == 201
    except Exception as e:
        print(f"❌ AI告警接收接口测试失败: {e}")
        return False

def test_alerts_list_api():
    """测试告警列表接口"""
    print("\n📋 测试告警列表接口")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/alerts/list/",
            timeout=10
        )
        print_response(response, "告警列表接口测试")
        return response.status_code in [200, 401]  # 200成功，401需要认证也是正常的
    except Exception as e:
        print(f"❌ 告警列表接口测试失败: {e}")
        return False

def test_alerts_stats_api():
    """测试告警统计接口"""
    print("\n📊 测试告警统计接口")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/alerts/stats/",
            timeout=10
        )
        print_response(response, "告警统计接口测试")
        return response.status_code in [200, 401]  # 200成功，401需要认证也是正常的
    except Exception as e:
        print(f"❌ 告警统计接口测试失败: {e}")
        return False

def test_alerts_test_api():
    """测试告警测试接口"""
    print("\n🧪 测试告警测试接口")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/alerts/test/",
            timeout=10
        )
        print_response(response, "告警测试接口")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 告警测试接口失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试告警管理API")
    print("=" * 60)
    
    # 测试服务器状态
    if not test_server_status():
        print("❌ 服务器未启动，请先启动服务器")
        return
    
    # 测试Swagger文档
    test_swagger_docs()
    
    # 测试各个API接口
    tests = [
        ("AI告警接收", test_ai_results_api),
        ("告警列表查询", test_alerts_list_api),
        ("告警统计", test_alerts_stats_api),
        ("告警测试", test_alerts_test_api),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    print(f"\n🎯 总体结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试都通过了！告警管理模块工作正常！")
    else:
        print("⚠️  部分测试失败，请检查相关问题")
    
    print(f"\n🌐 您可以访问以下地址进行进一步测试:")
    print(f"   - Swagger API文档: {BASE_URL}/swagger/")
    print(f"   - Django管理后台: {BASE_URL}/admin/")
    print(f"   - 告警列表API: {BASE_URL}/api/alerts/list/")

if __name__ == "__main__":
    main() 