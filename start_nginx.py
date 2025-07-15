import os
import time
import subprocess
import psutil
from pathlib import Path

def kill_process_by_port(port):
    """根据端口号杀死进程"""
    try:
        # 使用net_connections获取所有网络连接
        connections = psutil.net_connections()
        for conn in connections:
            if conn.laddr.port == port:
                try:
                    proc = psutil.Process(conn.pid)
                    print(f"终止端口 {port} 的进程 {conn.pid}")
                    proc.terminate()
                    time.sleep(0.5)  # 等待进程终止
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
    except Exception as e:
        print(f"清理端口 {port} 时出错: {str(e)}")

def is_port_in_use(port):
    """检查端口是否被占用"""
    try:
        # 使用net_connections获取所有网络连接
        connections = psutil.net_connections()
        return any(conn.laddr.port == port for conn in connections)
    except Exception as e:
        print(f"检查端口 {port} 时出错: {str(e)}")
        return False

def start_nginx():
    """启动nginx服务"""
    try:
        nginx_path = Path("nginx-rtmp-win32-1.2.1/nginx.exe")
        if not nginx_path.exists():
            print("错误: 找不到nginx.exe，请确保已正确安装nginx-rtmp")
            return False
        
        # 确保nginx配置文件存在
        nginx_conf = Path("nginx-rtmp-win32-1.2.1/conf/nginx.conf")
        if not nginx_conf.exists():
            print("正在复制nginx配置文件...")
            os.system("copy /Y nginx.conf nginx-1.24.0\\conf\\nginx.conf")
        
        # 确保logs目录存在
        logs_dir = Path("nginx-rtmp-win32-1.2.1/logs")
        logs_dir.mkdir(exist_ok=True)
        
        # 检查并清理端口
        ports_to_check = [8080, 1935]
        for port in ports_to_check:
            if is_port_in_use(port):
                print(f"端口 {port} 被占用，正在清理...")
                kill_process_by_port(port)
        
        # 停止已运行的nginx
        subprocess.run([str(nginx_path), "-s", "stop"], 
                      stderr=subprocess.PIPE, 
                      stdout=subprocess.PIPE)
        time.sleep(1)
        
        # 启动nginx
        print("正在启动nginx服务...")
        subprocess.Popen([str(nginx_path)], 
                        cwd=nginx_path.parent,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        time.sleep(2)
        print("\nNginx 启动成功")
        print("Nginx HTTP: http://localhost:8080")
        print("Nginx RTMP: rtmp://localhost:1935")
        return True
    except Exception as e:
        print(f"启动nginx时出错: {str(e)}")
        return False

def main():
    print("启动 Nginx 服务...")
    if start_nginx():
        print("\n按 Ctrl+C 停止服务...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n正在停止nginx...")
            nginx_path = Path("nginx-rtmp-win32-1.2.1/nginx.exe")
            if nginx_path.exists():
                subprocess.run([str(nginx_path), "-s", "stop"])
            print("Nginx已停止")

if __name__ == "__main__":
    main() 