#!/usr/bin/env python3
"""
快速测试已知可用的API接口
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_known_apis():
    """测试已知可用的API接口"""
    print("🚀 测试已知可用的API接口")
    print("=" * 50)
    
    # 1. 测试AI告警接收接口
    print("\n🤖 测试AI告警接收接口")
    ai_data = {
        "camera_id": "test_camera_001",
        "event_type": "stranger_intrusion", 
        "location": {"zone": "entrance", "coordinates": [100, 200]},
        "confidence": 0.95,
        "image_snapshot_url": "http://example.com/test_new.jpg"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/alerts/ai-results/",
            json=ai_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 201:
            print("✅ AI告警接收成功！")
            data = response.json()
            alert_id = data.get('id')
            print(f"📋 新创建的告警ID: {alert_id}")
            return alert_id
        else:
            print("❌ AI告警接收失败")
            print(f"错误: {response.text[:500]}")
    except Exception as e:
        print(f"❌ 请求异常: {e}")
    
    return None

def test_alerts_list():
    """测试告警列表接口（无认证）"""
    print("\n📋 测试告警列表接口")
    try:
        response = requests.get(f"{BASE_URL}/api/alerts/list/")
        print(f"状态码: {response.status_code}")
        if response.status_code == 401:
            print("✅ 认证系统正常工作（需要JWT token）")
        elif response.status_code == 200:
            print("✅ 接口可访问")
            data = response.json()
            print(f"📊 响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"⚠️  意外状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def test_swagger():
    """测试Swagger文档"""
    print("\n📖 测试Swagger文档")
    try:
        response = requests.get(f"{BASE_URL}/swagger/")
        if response.status_code == 200:
            print("✅ Swagger文档可访问")
            print(f"🌐 访问地址: {BASE_URL}/swagger/")
        else:
            print(f"❌ Swagger访问失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ Swagger访问异常: {e}")

def test_available_endpoints():
    """测试所有可用的告警相关端点"""
    print("\n🔍 测试所有已知的告警端点")
    endpoints = [
        ("GET", "/api/alerts/list/", "告警列表"),
        ("POST", "/api/alerts/ai-results/", "AI结果接收"),
        ("GET", "/api/alerts/1/", "告警详情"), 
        ("PUT", "/api/alerts/1/handle/", "告警处理"),
        ("PUT", "/api/alerts/1/update/", "告警更新"),
        ("GET", "/api/alerts/stats/", "告警统计"),
        ("GET", "/api/alerts/test/", "告警测试"),
    ]
    
    for method, endpoint, name in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            elif method == "POST":
                continue  # 跳过POST测试，避免重复创建数据
            elif method == "PUT":
                response = requests.put(f"{BASE_URL}{endpoint}", json={})
            
            status = response.status_code
            if status == 404:
                print(f"❌ {name}: 路由不存在 (404)")
            elif status == 401:
                print(f"✅ {name}: 需要认证 (401)")
            elif status == 200:
                print(f"✅ {name}: 正常访问 (200)")
            elif status == 405:
                print(f"⚠️  {name}: 方法不允许 (405)")
            else:
                print(f"⚠️  {name}: 状态码 {status}")
                
        except Exception as e:
            print(f"❌ {name}: 请求异常 - {e}")

def main():
    """主函数"""
    print("🔥 快速测试告警管理API")
    
    # 测试服务器状态
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ 服务器运行正常 (状态码: {response.status_code})")
    except:
        print("❌ 服务器连接失败")
        return
    
    # 执行各项测试
    test_swagger()
    alert_id = test_known_apis()
    test_alerts_list()
    test_available_endpoints()
    
    print("\n" + "=" * 50)
    print("🎯 测试完成！")
    print(f"📖 Swagger文档: {BASE_URL}/swagger/")
    print(f"🔧 Django管理: {BASE_URL}/admin/")
    
    if alert_id:
        print(f"🆔 测试告警ID: {alert_id}")
        print(f"🔍 测试详情: {BASE_URL}/api/alerts/{alert_id}/")
        print(f"⚙️  测试处理: {BASE_URL}/api/alerts/{alert_id}/handle/")

if __name__ == "__main__":
    main() 