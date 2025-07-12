@echo off
echo 启动所有服务...

echo 启动 Nginx...
start /B nginx-1.24.0\nginx.exe

echo 启动 AI 服务...
cd smart_station_platform\ai_service
start /B python app.py

echo 启动后端服务...
cd ..\backend
start /B python -m daphne -p 8000 smart_station.asgi:application

echo 启动前端服务...
cd ..\frontend
start /B npm run dev

echo 所有服务已启动！
echo Nginx: http://localhost:8080
echo AI 服务: http://localhost:8001
echo 后端服务: http://localhost:8000
echo 前端服务: http://localhost:5174 
echo 启动所有服务...

echo 启动 Nginx...
start /B nginx-1.24.0\nginx.exe

echo 启动 AI 服务...
cd smart_station_platform\ai_service
start /B python app.py

echo 启动后端服务...
cd ..\backend
start /B python -m daphne -p 8000 smart_station.asgi:application

echo 启动前端服务...
cd ..\frontend
start /B npm run dev

echo 所有服务已启动！
echo Nginx: http://localhost:8080
echo AI 服务: http://localhost:8001
echo 后端服务: http://localhost:8000
echo 前端服务: http://localhost:5174 
 