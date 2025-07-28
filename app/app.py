import os
import subprocess
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from logger import logger

app = Flask(__name__)

# --- 配置 ---
# 从环境变量加载配置，提供默认值以防万一
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
PANEL_USER = os.getenv('PANEL_USER', 'admin')
PANEL_PASSWORD = os.getenv('PANEL_PASSWORD', 'password')
SCRIPT_PATH = './L4D2_Manager_API.sh'

# --- 辅助函数：运行脚本 ---
def run_script(args):
    """一个安全的脚本运行器，返回JSON或错误信息"""
    command = ['bash', SCRIPT_PATH] + args
    print(f"[DEBUG] 执行脚本命令: {' '.join(command)}")
    
    try:
        # 检查脚本文件是否存在
        if not os.path.exists(SCRIPT_PATH):
            error_message = f"脚本文件不存在: {SCRIPT_PATH}"
            print(f"[ERROR] {error_message}")
            logger.log_script_execution(args, False, error_message=error_message)
            return jsonify({"error": error_message, "success": False}), 500
            
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(f"[DEBUG] 脚本执行成功，输出: {result.stdout[:200]}...")
        # 记录成功的脚本执行
        logger.log_script_execution(args, True, result.stdout)
        return jsonify(result.stdout)
    except subprocess.CalledProcessError as e:
        error_message = f"脚本执行失败: {e.stderr or e.stdout}"
        print(f"[ERROR] {error_message}")
        print(f"[ERROR] 返回码: {e.returncode}")
        # 记录失败的脚本执行
        logger.log_script_execution(args, False, error_message=error_message)
        return jsonify({"error": error_message, "success": False, "returncode": e.returncode}), 500
    except Exception as e:
        error_message = f"未知错误: {str(e)}"
        print(f"[ERROR] {error_message}")
        import traceback
        print(f"[ERROR] 堆栈跟踪: {traceback.format_exc()}")
        # 记录异常的脚本执行
        logger.log_script_execution(args, False, error_message=error_message)
        return jsonify({"error": error_message, "success": False}), 500

# --- 认证 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == PANEL_USER and password == PANEL_PASSWORD:
            session['logged_in'] = True
            # 记录成功登录
            logger.log_login_attempt(username, True)
            return redirect(url_for('dashboard'))
        else:
            # 记录失败登录
            logger.log_login_attempt(username, False)
            return render_template('login.html', error="用户名或密码错误！")
    return render_template('login.html')

@app.route('/logout')
def logout():
    # 记录登出操作
    logger.log_logout()
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- 页面路由 ---
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/plugins')
@login_required
def plugins_page():
    return render_template('plugins.html')

@app.route('/logs')
@login_required
def logs_page():
    return render_template('logs.html')

# --- API 路由 ---
@app.route('/api/status', methods=['GET'])
@login_required
def api_get_status():
    print(f"[DEBUG] API调用: /api/status")
    try:
        # 记录API调用
        logger.log_api_call('/api/status', 'GET')
        return run_script(['get_status'])
    except Exception as e:
        error_message = f"获取状态失败: {str(e)}"
        print(f"[ERROR] {error_message}")
        import traceback
        print(f"[ERROR] 堆栈跟踪: {traceback.format_exc()}")
        return jsonify({"error": error_message, "success": False}), 500

@app.route('/api/instances', methods=['GET'])
@login_required
def api_get_instances():
    print(f"[DEBUG] API调用: /api/instances")
    try:
        # 记录API调用
        logger.log_api_call('/api/instances', 'GET')
        return run_script(['get_instances'])
    except Exception as e:
        error_message = f"获取实例列表失败: {str(e)}"
        print(f"[ERROR] {error_message}")
        import traceback
        print(f"[ERROR] 堆栈跟踪: {traceback.format_exc()}")
        return jsonify({"error": error_message, "success": False}), 500

@app.route('/api/plugins', methods=['GET'])
@login_required
def api_get_plugins():
    print(f"[DEBUG] API调用: /api/plugins")
    try:
        # 记录API调用
        logger.log_api_call('/api/plugins', 'GET')
        return run_script(['get_plugins'])
    except Exception as e:
        error_message = f"获取插件列表失败: {str(e)}"
        print(f"[ERROR] {error_message}")
        import traceback
        print(f"[ERROR] 堆栈跟踪: {traceback.format_exc()}")
        return jsonify({"error": error_message, "success": False}), 500

@app.route('/api/action', methods=['POST'])
@login_required
def api_action():
    data = request.get_json()
    action = data.get('action')
    payload = data.get('payload')

    if not action:
        # 记录错误的API调用
        logger.log_api_call('/api/action', 'POST', {}, "failed", "缺少 'action' 参数")
        return jsonify({"error": "缺少 'action' 参数"}), 400

    # 记录API调用参数
    api_params = {"action": action, "payload": payload}
    
    # 对于长时间运行的部署任务，使用流式响应
    if action == 'deploy_server':
        # 记录部署开始
        logger.log_api_call('/api/action', 'POST', api_params, "started", "开始部署服务器")
        
        def generate_log():
            command = ['bash', SCRIPT_PATH, action]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield f"data: {line}\n\n"
            process.stdout.close()
            return_code = process.wait()
            
            # 记录部署结果
            if return_code == 0:
                logger.log_api_call('/api/action', 'POST', api_params, "completed", "部署服务器完成")
            else:
                logger.log_api_call('/api/action', 'POST', api_params, "failed", f"部署服务器失败，退出码: {return_code}")
        
        return Response(generate_log(), mimetype='text/event-stream')

    # 对于快速完成的任务
    else:
        command = ['bash', SCRIPT_PATH, action]
        if payload:
            command.append(payload)
        
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            # 记录成功的API调用
            logger.log_api_call('/api/action', 'POST', api_params, "success")
            return jsonify({"success": True, "message": result.stdout})
        except subprocess.CalledProcessError as e:
            error_message = e.stderr or e.stdout
            # 记录失败的API调用
            logger.log_api_call('/api/action', 'POST', api_params, "failed", error_message)
            return jsonify({"success": False, "message": error_message}), 400


# --- 日志管理API ---
@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """获取操作日志"""
    try:
        limit = int(request.args.get('limit', 100))
        action_filter = request.args.get('action')
        
        logs = logger.get_logs(limit=limit, action_filter=action_filter)
        
        # 记录日志查看操作
        logger.log_api_call('/api/logs', 'GET', {
            'limit': limit, 
            'action_filter': action_filter
        })
        
        return jsonify({
            "success": True,
            "logs": logs,
            "total": len(logs)
        })
    except Exception as e:
        error_message = f"获取日志失败: {str(e)}"
        logger.log_api_call('/api/logs', 'GET', {}, "failed", error_message)
        return jsonify({"success": False, "message": error_message}), 500

@app.route('/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    """清空操作日志"""
    try:
        logger.clear_logs()
        return jsonify({"success": True, "message": "日志已清空"})
    except Exception as e:
        error_message = f"清空日志失败: {str(e)}"
        return jsonify({"success": False, "message": error_message}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)