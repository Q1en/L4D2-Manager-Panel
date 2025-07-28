#!/bin/bash

# =================================================================
# L4D2 服务器与插件管理器 API 版本 (非交互式)
# 改编自: L4D2_Manager.sh 2627 - Polaris
# 功能: 为Web面板提供后端执行接口
# =================================================================

# --- Bash 版本检查 ---
if ((BASH_VERSINFO[0] < 4)); then
    echo "错误: 此脚本需要 Bash 4.0 或更高版本才能运行。"
    exit 1
fi

# ########################## 用户配置区 ##########################
ServerRoot="/home/steam/l4d2server"
SteamCMDDir="/home/steam/steamcmd"
declare -A ServerInstances=(
    ["主服_战役"]="
        Port=27015
        HostName='[CN] My L4D2 Campaign Server'
        MaxPlayers=8
        StartMap='c1m1_hotel'
        ExtraParams='+sv_gametypes \"coop,realism,survival\"'
    "
    ["副服_对抗"]="
        Port=27016
        HostName='[CN] My L4D2 Versus Server'
        MaxPlayers=8
        StartMap='c5m1_waterfront'
        ExtraParams='+sv_gametypes \"versus,teamversus,scavenge\"'
    "
)
# #################################################################


# --- 脚本变量定义 ---
L4d2Dir="$ServerRoot/left4dead2"
ScriptDir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PluginSourceDir="$ScriptDir/Available_Plugins"
ReceiptsDir="$ScriptDir/Installed_Receipts"
InstallerDir="$ScriptDir/SourceMod_Installers"

# 确保目录存在
mkdir -p "$PluginSourceDir" "$ReceiptsDir" "$InstallerDir"

# --- 核心功能函数 ---

function Deploy-L4D2Server_NonInteractive() {
    echo "--- 开始部署/更新 L4D2 服务器 ---"
    local steamcmd_executable="$SteamCMDDir/steamcmd.sh"

    if [ ! -f "$steamcmd_executable" ]; then
        echo "未找到 SteamCMD，尝试自动下载..."
        mkdir -p "$SteamCMDDir"
        wget -O "$SteamCMDDir/steamcmd_linux.tar.gz" "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
        tar -xvzf "$SteamCMDDir/steamcmd_linux.tar.gz" -C "$SteamCMDDir"
        rm "$SteamCMDDir/steamcmd_linux.tar.gz"
    fi

    mkdir -p "$ServerRoot"

    # 优先使用环境变量中的用户名和密码
    if [ -n "$STEAM_USER" ] && [ -n "$STEAM_PASSWORD" ]; then
        echo "使用账户: $STEAM_USER"
        unbuffer "$steamcmd_executable" +force_install_dir "$ServerRoot" +login "$STEAM_USER" "$STEAM_PASSWORD" +app_update 222860 validate +quit | sed -u 's/\x1b\[[0-9;]*[a-zA-Z]//g'
    else
        # 否则，使用匿名登录
        echo "使用匿名 (anonymous) 登录。"
        unbuffer "$steamcmd_executable" +force_install_dir "$ServerRoot" +login anonymous +app_update 222860 validate +quit | sed -u 's/\x1b\[[0-9;]*[a-zA-Z]//g'
    fi
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "--- L4D2 服务器文件部署/更新成功! ---"
    else
        echo "--- SteamCMD 执行失败，请检查以上日志。 ---"
        return 1
    fi
}

function Start-L4D2ServerInstance_NonInteractive() {
    local instanceName="$1"
    if [ ! -v "ServerInstances[$instanceName]" ]; then
        echo "错误: 未在配置中找到名为 '$instanceName' 的实例。"
        exit 1
    fi
    eval "${ServerInstances[$instanceName]}" # 加载实例配置

    local session_name="l4d2_manager_${instanceName}"
    if screen -ls | grep -q "\.$session_name"; then
        echo "错误: 名为 '$session_name' 的 screen 会话已在运行。"
        exit 1
    fi

    local srcds_path="./srcds_run"
    local srcdsArgs="-console -game left4dead2 -port $Port +maxplayers $MaxPlayers +map $StartMap +hostname \"$HostName\" $ExtraParams"

    echo "准备在 Screen 会话 '$session_name' 中启动服务器..."
    echo "执行命令: $srcds_path $srcdsArgs"
    (cd "$ServerRoot" && screen -dmS "$session_name" $srcds_path $srcdsArgs)
    sleep 1
    if screen -ls | grep -q "\.$session_name"; then
        echo "成功! 实例 '$instanceName' 已在 screen 会话 '$session_name' 中启动。"
    else
        echo "错误: 启动服务器失败。请检查 screen 和服务器文件是否正常。"
        exit 1
    fi
}

function Stop-L4D2ServerInstance_NonInteractive() {
    local instanceName="$1"
    local session_name="l4d2_manager_${instanceName}"
    if ! screen -ls | grep -q "\.$session_name"; then
        echo "错误: 未找到名为 '$session_name' 的 screen 会话。"
        exit 1
    fi
    echo "正在向会话 '$session_name' 发送 quit 指令..."
    screen -S "$session_name" -X stuff $'quit\n'
    echo "成功! 停止指令已发送至实例 '$instanceName'。"
}

function Invoke-PluginInstallation() {
    local pluginName="$1"
    local pluginPath="$PluginSourceDir/$pluginName"
    local receiptPath="$ReceiptsDir/$pluginName.receipt"
    if [ ! -d "$pluginPath" ]; then
      echo "错误: 找不到插件源目录 '$pluginPath'。"
      exit 1
    fi
    echo "--- 开始安装插件 '$pluginName' ---"
    echo "创建文件清单..."
    (cd "$pluginPath" && find . -type f | sed 's|^\./||') > "$receiptPath"
    if [ $? -ne 0 ]; then
        echo "错误! 创建插件清单 '$receiptPath' 失败。"
        rm -f "$receiptPath"
        exit 1
    fi
    
    echo "正在将文件移动到服务器目录..."
    rsync -a "$pluginPath/" "$ServerRoot/"
    
    if [ $? -eq 0 ]; then
        # 成功之后删除源目录
        rm -rf "$pluginPath"
        echo "--- 插件 '$pluginName' 安装成功! ---"
    else
        echo "--- 错误! 安装插件 '$pluginName' 时文件操作失败。 ---"
        rm -f "$receiptPath"
        exit 1
    fi
}

function Invoke-PluginUninstallation() {
    local pluginName="$1"
    local receiptPath="$ReceiptsDir/$pluginName.receipt"
    if [ ! -f "$receiptPath" ]; then
        echo "错误: 找不到插件清单 '$receiptPath'。无法卸载。"
        exit 1
    fi
    
    echo "--- 开始卸载插件 '$pluginName' ---"
    
    local pluginReclaimFolder="$PluginSourceDir/$pluginName"
    mkdir -p "$pluginReclaimFolder"

    while IFS= read -r relativePath || [[ -n "$relativePath" ]]; do
        [ -z "$relativePath" ] && continue

        local serverFile="$ServerRoot/$relativePath"
        local destinationFile="$pluginReclaimFolder/$relativePath"
        
        if [ -f "$serverFile" ]; then
            # 确保目标目录存在
            mkdir -p "$(dirname "$destinationFile")"
            # 移动文件
            mv "$serverFile" "$destinationFile"
            # echo "已移回: $destinationFile" # 可以取消注释用于调试
        fi
    done < "$receiptPath"

    # 清理服务器上可能残留的空目录
    while IFS= read -r relativePath; do
        [ -z "$relativePath" ] && continue
        local dirOnServer="$ServerRoot/$(dirname "$relativePath")"
        # 如果目录存在且为空，则尝试删除
        if [ -d "$dirOnServer" ] && [ -z "$(ls -A "$dirOnServer")" ]; then
            rmdir "$dirOnServer" 2>/dev/null
        fi
    done < <(sort -r "$receiptPath") # 反向排序，以便先处理子目录

    rm -f "$receiptPath"
    echo "--- 插件 '$pluginName' 卸载成功! ---"
}

function Install-SourceModAndMetaMod_NonInteractive() {
    echo "--- 开始安装 SourceMod & MetaMod ---"
    # 确保安装目录存在
    mkdir -p "$InstallerDir"
    
    local metamod_tar
    metamod_tar=$(find "$InstallerDir" -maxdepth 1 -name "mmsource-*.tar.gz" | sort -V | tail -n 1)
    
    if [ -n "$metamod_tar" ]; then
        echo "发现 MetaMod: $(basename "$metamod_tar")"
        if tar -xzf "$metamod_tar" -C "$L4d2Dir"; then
            echo "MetaMod 解压完成。"
            
            # 创建 metamod.vdf
            mkdir -p "$L4d2Dir/addons"
            echo -e "\"Plugin\"\n{\n\t\"file\"\t\"addons/metamod/bin/server\"\n}" > "$L4d2Dir/addons/metamod.vdf"
            echo "'metamod.vdf' 创建成功。"
        else
            echo "错误: 解压 MetaMod 时出错。"
        fi
    else
        echo "警告: 在 '$InstallerDir' 中未找到 MetaMod 安装包 (mmsource-*.tar.gz)。"
    fi
    
    local sourcemod_tar
    sourcemod_tar=$(find "$InstallerDir" -maxdepth 1 -name "sourcemod-*.tar.gz" | sort -V | tail -n 1)

    if [ -n "$sourcemod_tar" ]; then
        echo "发现 SourceMod: $(basename "$sourcemod_tar")"
        if tar -xzf "$sourcemod_tar" -C "$L4d2Dir"; then
            echo "SourceMod 解压完成。"
        else
            echo "错误: 解压 SourceMod 时出错。"
        fi
    else
        echo "警告: 在 '$InstallerDir' 中未找到 SourceMod 安装包 (sourcemod-*.tar.gz)。"
    fi
    
    echo "--- 安装流程执行完毕 ---"
}

# --- API 调用入口 ---
ACTION="$1"
shift

case "$ACTION" in
    get_status)
        server_deployed="false"
        sm_installed="false"
        if [ -f "$ServerRoot/srcds_run" ]; then server_deployed="true"; fi
        if [ -f "$L4d2Dir/addons/metamod.vdf" ]; then sm_installed="true"; fi
        echo "{\"serverDeployed\": $server_deployed, \"smInstalled\": $sm_installed}"
        ;;

    get_instances)
        # 输出所有定义的实例及其运行状态
        json="{"
        first=true
        for name in "${!ServerInstances[@]}"; do
            session_name="l4d2_manager_${name}"
            running="false"
            if screen -ls | grep -q "\.$session_name"; then
                running="true"
            fi
            eval "${ServerInstances[$name]}" # 加载端口等信息
            if ! $first; then json+=","; fi
            json+="\"$name\": {\"port\": \"$Port\", \"hostname\": \"$HostName\", \"map\": \"$StartMap\", \"maxplayers\": \"$MaxPlayers\", \"running\": $running}"
            first=false
        done
        json+="}"
        echo "$json"
        ;;

    get_plugins)
        # 输出可用和已安装的插件列表
        available="["
        first=true
        for d in "$PluginSourceDir"/*/; do
            [ -d "$d" ] || continue
            pname=$(basename "$d")
            # 只有不在收据里的才是“可安装”
            if [ ! -f "$ReceiptsDir/$pname.receipt" ]; then
                if ! $first; then available+=","; fi
                available+="\"$pname\""
                first=false
            fi
        done
        available+="]"

        installed="["
        first=true
        for f in "$ReceiptsDir"/*.receipt; do
            [ -f "$f" ] || continue
            pname=$(basename "$f" .receipt)
            if ! $first; then installed+=","; fi
            installed+="\"$pname\""
            first=false
        done
        installed+="]"

        echo "{\"available\": $available, \"installed\": $installed}"
        ;;
    
    deploy_server)
        Deploy-L4D2Server_NonInteractive
        ;;

    start_instance)
        Start-L4D2ServerInstance_NonInteractive "$1"
        ;;

    stop_instance)
        Stop-L4D2ServerInstance_NonInteractive "$1"
        ;;
    
    install_plugin)
        Invoke-PluginInstallation "$1"
        ;;

    uninstall_plugin)
        Invoke-PluginUninstallation "$1"
        ;;
    install_sourcemod)
        Install-SourceModAndMetaMod_NonInteractive
        ;;

    *)
        echo "错误: 未知的 API Action: $ACTION"
        exit 1
        ;;
esac
