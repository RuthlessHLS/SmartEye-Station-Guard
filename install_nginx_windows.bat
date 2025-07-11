@echo off
echo 正在下载带RTMP模块的 Nginx...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/illuspas/nginx-rtmp-win32/releases/download/v1.5.16.5/nginx-rtmp-win32-1.5.16.5.zip' -OutFile 'nginx-rtmp.zip'"

echo 正在清理旧文件...
if exist "nginx-1.24.0" rmdir /s /q "nginx-1.24.0"

echo 正在解压 Nginx...
powershell -Command "Expand-Archive -Path 'nginx-rtmp.zip' -DestinationPath 'nginx-1.24.0' -Force"

echo 正在创建必要的目录...
mkdir nginx-1.24.0\temp\hls 2>nul

echo 复制配置文件...
copy /Y nginx.conf nginx-1.24.0\conf\nginx.conf

echo 安装完成！
echo 请运行 start_services.bat 启动所有服务 