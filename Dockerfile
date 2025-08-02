# 使用一个包含 Python 的官方基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 更新包列表并安装 Shell 脚本所需要的依赖
# screen: 用于在后台运行 srcds_run
# rsync, wget, tar: 用于插件和服务器安装
# ca-certificates: 用于HTTPS下载
# sudo: 某些脚本或命令可能需要
# unzip, unrar-free: 用于文件管理器的解压缩功能
# 开启i386架构，并安装32位运行库
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    screen \
    rsync \
    wget \
    tar \
    ca-certificates \
    sudo \
    expect \
    unzip \
    unrar-free \
    lib32gcc-s1 \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖文件并安装
COPY ./app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有应用文件到工作目录
COPY ./app .

# 授予脚本执行权限
RUN chmod +x ./L4D2_Manager_API.sh

# 暴露端口
EXPOSE 8080

# 容器启动时运行 Flask 应用，使用 gunicorn 作为生产环境的 WSGI 服务器
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
