#!/usr/bin/env python
"""
数据大屏API测试脚本
用于测试数据大屏相关的API接口
"""

import requests
import json
from datetime import datetime, timedelta

# 配置
BASE_URL = 'http://localhost:8000/api/data-analysis'
TOKEN = 'your_token_here'  # 请替换为实际的token
HEADERS = {
    'Authorization': f'Token {TOKEN}',
    'Content-Type': 'application/json'
}

def test_dashboard_api():
    """测试数据大屏主接口"""
    print("=== 测试数据大屏主接口 ===")
    
    try:
        # 测试获取当天数据
        response = requests.get(f'{BASE_URL}/dashboard/', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 数据大屏接口测试成功")
            print(f"热力图数据点数量: {len(data.get('heatmap', []))}")
            print(f"交通趋势数据点数量: {len(data.get('traffic_trend', []))}")
            print(f"平均速度: {data.get('avg_speed', 0)}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_trajectory_api():
    """测试轨迹回放接口"""
    print("\n=== 测试轨迹回放接口 ===")
    
    try:
        # 测试获取车辆轨迹
        vehicle_id = 'VEH_001'
        response = requests.get(f'{BASE_URL}/trajectory/{vehicle_id}/', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 轨迹回放接口测试成功")
            print(f"轨迹点数量: {len(data.get('trajectory', []))}")
            print(f"车辆信息: {data.get('vehicle_info', {})}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_traffic_data_api():
    """测试交通数据接口"""
    print("\n=== 测试交通数据接口 ===")
    
    try:
        # 测试获取交通数据
        response = requests.get(f'{BASE_URL}/traffic-data/?limit=5', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 交通数据接口测试成功")
            print(f"数据条数: {len(data.get('data', []))}")
            print(f"总数据量: {data.get('total', 0)}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_weather_data_api():
    """测试天气数据接口"""
    print("\n=== 测试天气数据接口 ===")
    
    try:
        # 测试获取天气数据
        response = requests.get(f'{BASE_URL}/weather-data/?days=3', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 天气数据接口测试成功")
            print(f"数据条数: {len(data.get('data', []))}")
            print(f"查询日期范围: {data.get('date_range', {})}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_config_api():
    """测试配置接口"""
    print("\n=== 测试配置接口 ===")
    
    try:
        # 测试获取配置
        response = requests.get(f'{BASE_URL}/config/', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 配置接口测试成功")
            print(f"配置名称: {data.get('name', '')}")
            print(f"是否激活: {data.get('is_active', False)}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_realtime_api():
    """测试实时数据接口"""
    print("\n=== 测试实时数据接口 ===")
    
    try:
        # 测试获取实时数据
        response = requests.get(f'{BASE_URL}/realtime/', headers=HEADERS)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 实时数据接口测试成功")
            print(f"实时交通数据条数: {len(data.get('realtime_traffic', []))}")
            print(f"当前平均速度: {data.get('current_avg_speed', 0)}")
            print(f"最后更新时间: {data.get('last_updated', '')}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_create_traffic_data():
    """测试创建交通数据"""
    print("\n=== 测试创建交通数据 ===")
    
    try:
        # 测试数据
        test_data = {
            'location_lat': 39.9042,
            'location_lng': 116.4074,
            'intensity': 0.8,
            'traffic_count': 1200,
            'avg_speed': 45.5
        }
        
        response = requests.post(f'{BASE_URL}/traffic-data/', headers=HEADERS, json=test_data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print("✅ 创建交通数据测试成功")
            print(f"创建的数据ID: {data.get('id', '')}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def test_create_weather_data():
    """测试创建天气数据"""
    print("\n=== 测试创建天气数据 ===")
    
    try:
        # 测试数据
        test_data = {
            'weather_type': '晴',
            'temperature': 25.0,
            'humidity': 60.0,
            'wind_speed': 5.0
        }
        
        response = requests.post(f'{BASE_URL}/weather-data/', headers=HEADERS, json=test_data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print("✅ 创建天气数据测试成功")
            print(f"创建的数据ID: {data.get('id', '')}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

def main():
    """主测试函数"""
    print("🚀 开始测试数据大屏API")
    print("=" * 50)
    
    # 检查服务器连接
    try:
        response = requests.get(f'{BASE_URL}/dashboard/', headers=HEADERS, timeout=5)
        if response.status_code == 401:
            print("⚠️  认证失败，请检查TOKEN是否正确")
            print("请修改脚本中的TOKEN变量为有效的认证token")
            return
        elif response.status_code == 404:
            print("⚠️  服务器未启动或URL不正确")
            print("请确保Django服务器正在运行，并且URL配置正确")
            return
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        print("请确保Django服务器正在运行在 http://localhost:8000")
        return
    except Exception as e:
        print(f"❌ 连接测试失败: {str(e)}")
        return
    
    # 执行所有测试
    test_dashboard_api()
    test_trajectory_api()
    test_traffic_data_api()
    test_weather_data_api()
    test_config_api()
    test_realtime_api()
    test_create_traffic_data()
    test_create_weather_data()
    
    print("\n" + "=" * 50)
    print("🎉 所有测试完成！")

if __name__ == '__main__':
    main() 