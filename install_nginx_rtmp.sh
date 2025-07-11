#!/bin/bash

# 安装依赖
sudo apt update
sudo apt install -y build-essential libpcre3 libpcre3-dev libssl-dev zlib1g-dev

# 下载 Nginx 和 RTMP 模块
wget http://nginx.org/download/nginx-1.24.0.tar.gz
wget https://github.com/arut/nginx-rtmp-module/archive/master.zip

# 解压
tar -xf nginx-1.24.0.tar.gz
unzip master.zip

# 编译安装
cd nginx-1.24.0
./configure --with-http_ssl_module --add-module=../nginx-rtmp-module-master
make
sudo make install

# 创建必要的目录
sudo mkdir -p /tmp/hls
sudo chmod 777 /tmp/hls 