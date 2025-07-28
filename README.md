# L4D2 管理面板

该项目用于管理 Left 4 Dead 2 游戏服务器的可视化面板。

## 快速启动

### 前置条件
- Python 3.10+
- Docker（可选）

### 本地运行
```bash
# 安装依赖
pip install -r app/requirements.txt

# 启动应用
python app/app.py
```

### Docker运行
```bash
docker-compose up --build
```

## 功能特性
- 实时监控服务器状态
- 插件管理系统
- 玩家数据统计

## 目录结构
```
├── Dockerfile
├── app/
│   ├── L4D2_Manager_API.sh
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
├── docker-compose.yml
└── ...
```