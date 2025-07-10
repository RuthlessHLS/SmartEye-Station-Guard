@echo off
REM 设置AI资产目录环境变量

echo 设置AI资产目录环境变量...

if "%1"=="" (
    echo 错误：请提供资产目录路径作为参数
    echo 用法: setup_env.bat D:\path\to\assets
    exit /b 1
)

REM 检查目录是否存在
if not exist "%1" (
    echo 警告：目录 "%1" 不存在，将尝试创建它
    mkdir "%1" 2>nul
    if not exist "%1" (
        echo 错误：无法创建目录 "%1"
        exit /b 1
    )
)

REM 创建模型子目录
if not exist "%1\models\torch" (
    echo 创建模型子目录...
    mkdir "%1\models\torch" 2>nul
)

REM 设置环境变量
set G_DRIVE_ASSET_PATH=%1
echo 成功设置 G_DRIVE_ASSET_PATH = %G_DRIVE_ASSET_PATH%

REM 提示用户下载模型
echo.
echo 请确保以下模型文件存在于 %G_DRIVE_ASSET_PATH%\models\torch 目录中：
echo - yolov8n.pt (通用目标检测模型)
echo - yolov8n-fire.pt (专用火焰检测模型，可选)
echo.
echo 您可以使用以下命令下载模型：
echo python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
echo.

echo 环境设置完成。 