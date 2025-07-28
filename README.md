# L4D2 管理面板

一个现代化、响应式的 Left 4 Dead 2 服务器可视化管理面板。它通过一个简洁的 Web 界面，简化了服务器的部署、配置、实例管理和插件安装等操作，专为服主设计。

仪表盘界面截图：
<img width="2548" height="1411" alt="screenshot-1753721219912" src="https://github.com/user-attachments/assets/16df34ef-a0fb-4e76-a321-bd7abefcc4ce" />

## ✨ 功能特性

  - **仪表盘概览**: 实时查看服务器核心状态，包括服务器文件是否部署、插件平台是否安装、运行中的实例数量和已安装的插件总数。
  - **一键部署**: 通过网页按钮直接调用 SteamCMD 部署或更新求生之路2服务器，并提供实时的日志输出。
  - **实例管理**: 在网页上定义和管理多个服务器实例，可以独立启动或停止每个实例。
  - **插件管理系统**:
      - 自动检测可安装的插件。
      - 提供清晰的“可安装”和“已安装”插件列表。
      - 支持批量安装和卸载插件。
  - **插件平台安装**: 自动检测安装包并执行 SourceMod 和 MetaMod 的安装与更新。
  - **操作日志**: 详细记录所有面板操作，包括登录尝试、API 调用、脚本执行等。支持按类型过滤、导出和清空日志。
  - **容器化部署**: 提供 `Dockerfile` 和 `docker-compose.yml`，实现与宿主机环境的隔离，简化部署流程。
  - **安全认证**: 具备独立的面板登录认证机制。

## 🚀 快速启动 (推荐使用 Docker)

使用 Docker Compose 是最推荐的运行方式，它能自动处理所有依赖和配置。

### 前置条件

  - [Docker](https://www.docker.com/) 和 [Docker Compose](https://docs.docker.com/compose/)
  - Git

### 部署步骤

1.  **克隆项目仓库**

    ```bash
    git clone https://github.com/Q1en/L4D2-Manager-Panel.git
    cd L4D2-Manager-Panel
    ```

2.  **创建挂载目录**
    面板需要将服务器文件和 SteamCMD 保留在宿主机上，以防止容器重建时丢失。请在宿主机上创建这些目录。

    ```bash
    mkdir -p /home/steam/l4d2server
    mkdir -p /home/steam/steamcmd
    ```

    > **注意**: 如果您使用其他路径，请务必同步修改 `docker-compose.yml` 文件中的 `volumes` 部分。

3.  **配置环境变量**
    打开 `docker-compose.yml` 文件，根据您的需求修改 `environment` 部分：

      - `PANEL_USER`: 面板的登录用户名。
      - `PANEL_PASSWORD`: 面板的登录密码。
      - `STEAM_USER`: 用于登录 SteamCMD 的用户名（建议使用小号）。
      - `STEAM_PASSWORD`: Steam 账户的密码。
      - `TZ`: 设置容器的时区，例如 `Asia/Shanghai`。

4.  **构建并启动容器**

    ```bash
    docker compose up --build -d
    ```

5.  **访问面板**
    启动成功后，在浏览器中打开 `http://<你的服务器IP>:8080` 即可访问管理面板。

## ⚙️ 配置指南

### 1\. 服务器实例配置

你可以在 `app/L4D2_Manager_API.sh` 脚本中定义多个服务器实例。
在 `ServerInstances` 关联数组中添加或修改条目：

```bash
declare -A ServerInstances=(
    ["主服_战役"]="
        Port=27015
        HostName='[CN] My L4D2 Campaign Server'
        MaxPlayers=8
        StartMap='c1m1_hotel'
        ExtraParams='+sv_gametypes \"coop,realism,survival\"'
    "
    # 在这里添加更多实例...
)
```

### 2\. 插件和 SourceMod 配置

  - **SourceMod/MetaMod 安装包**: 将 `sourcemod-*.tar.gz` 和 `mmsource-*.tar.gz` 文件放入 `app/SourceMod_Installers` 目录中。脚本会自动选择最新版本进行安装。
  - **插件**: 将解压后的插件文件夹（例如，一个包含 `addons`、`cfg` 等子目录的文件夹）放入 `app/Available_Plugins` 目录中。面板会自动将其识别为可安装插件。

## 🛠️ 技术栈

  - **后端**: Flask
  - **前端**: 原生 HTML/CSS/JavaScript, [SweetAlert2](https://sweetalert2.github.io/), [Feather Icons](https://feathericons.com/)
  - **核心逻辑**: Bash Script (`screen` 用于会话管理)
  - **容器化**: Docker / Docker Compose

## 📁 目录结构

```
.
├── app/
│   ├── L4D2_Manager_API.sh     # 核心功能的 Shell 脚本
│   ├── app.py                  # Flask 应用主文件
│   ├── logger.py               # 日志记录器
│   ├── requirements.txt        # Python 依赖
│   ├── Available_Plugins/      # 存放可用插件
│   ├── Installed_Receipts/     # 插件安装回执，请勿修改
│   ├── SourceMod_Installers/   # 存放插件平台安装包
│   ├── logs/                   # 存放日志
│   ├── static/
│   │   └── style.css           # 全局样式表
│   └── templates/
│       ├── dashboard.html      # 仪表盘页面
│       ├── login.html          # 登录页面
│       ├── logs.html           # 日志页面
│       └── plugins.html        # 插件管理页面
├── docker-compose.yml          # Docker Compose 配置文件
└── Dockerfile                  # Docker 镜像定义文件
```

## 🤝 贡献

欢迎提交 Pull Requests 或 Issues。

## 📄 许可证

本项目采用 [AGPLV3](https://www.gnu.org/licenses/agpl-3.0.html) 许可证。
