import json
import os
import subprocess
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from logger import logger

app = Flask(__name__)

# --- 配置 ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
PANEL_USER = os.getenv('PANEL_USER', 'admin')
PANEL_PASSWORD = os.getenv('PANEL_PASSWORD', 'password')
SCRIPT_PATH = './L4D2_Manager_API.sh'
SERVER_ROOT = '/home/steam/l4d2server'
app.config['UPLOAD_FOLDER'] = SERVER_ROOT

# --- 辅助函数：运行脚本 ---
def run_script(args, payload_stdin=None):
    command = ['bash', SCRIPT_PATH] + args
    logger.log_script_execution(args, True, f"Executing command: {' '.join(command)}")

    try:
        if not os.path.exists(SCRIPT_PATH):
            raise FileNotFoundError(f"脚本文件不存在: {SCRIPT_PATH}")

        process_input = str(payload_stdin) if payload_stdin is not None else None

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            input=process_input
        )

        if result.returncode != 0:
            error_message = result.stderr or result.stdout or "未知脚本错误"
            logger.log_script_execution(args, False, error_message=error_message)
            return {"success": False, "message": error_message.strip()}

        logger.log_script_execution(args, True, result.stdout)
        return {"success": True, "output": result.stdout.strip()}

    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        error_message = f"执行脚本时发生内部错误: {str(e)}"
        logger.log_script_execution(args, False, error_message=error_message)
        return {"success": False, "message": error_message}


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
            logger.log_login_attempt(username, True)
            return redirect(url_for('dashboard'))
        else:
            logger.log_login_attempt(username, False)
            return render_template('login.html', error="用户名或密码错误！")
    return render_template('login.html')

@app.route('/logout')
def logout():
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

@app.route('/files')
@login_required
def files_page():
    return render_template('files.html')


# --- API 路由 ---

@app.route('/api/status', methods=['GET'])
@login_required
def api_get_status():
    logger.log_api_call('/api/status', 'GET')
    result = run_script(['get_status'])
    if not result['success']:
        return jsonify({"success": False, "error": result['message']}), 500
    try:
        return jsonify(json.loads(result['output']))
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "无法解析脚本状态输出"}), 500

@app.route('/api/instances', methods=['GET'])
@login_required
def api_get_instances():
    logger.log_api_call('/api/instances', 'GET')
    result = run_script(['get_instances'])
    if not result['success']:
        return jsonify({"success": False, "error": result['message']}), 500
    try:
        return jsonify(json.loads(result['output']))
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "无法解析实例列表"}), 500

@app.route('/api/plugins', methods=['GET'])
@login_required
def api_get_plugins():
    logger.log_api_call('/api/plugins', 'GET')
    result = run_script(['get_plugins'])
    if not result['success']:
        return jsonify({"success": False, "error": result['message']}), 500
    try:
        plugins_data = json.loads(result['output'])
        return jsonify(plugins_data)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "无法解析插件列表"}), 500


@app.route('/api/action', methods=['POST'])
@login_required
def api_action():
    data = request.get_json()
    action = data.get('action')
    payload = data.get('payload')
    api_params = {"action": action, "payload": payload}

    if not action:
        logger.log_api_call('/api/action', 'POST', api_params, "failed", "缺少 'action' 参数")
        return jsonify({"error": "缺少 'action' 参数", "success": False}), 400

    # 对于长时间运行的部署任务，使用流式响应
    if action == 'deploy_server':
        logger.log_api_call('/api/action', 'POST', api_params, "started", "开始部署服务器")
        def generate_log():
            command = ['bash', SCRIPT_PATH, action]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield f"data: {line}\n\n"
            process.stdout.close()
            rc = process.wait()
            status = "completed" if rc == 0 else "failed"
            logger.log_api_call('/api/action', 'POST', api_params, status, f"部署完成，退出码: {rc}")
        return Response(generate_log(), mimetype='text/event-stream')

    # 对于快速完成的任务
    else:
        command_args = [action]
        if payload:
            command_args.append(payload)
        
        result = run_script(command_args)
        
        if result['success']:
            logger.log_api_call('/api/action', 'POST', api_params, "success")
            return jsonify({"success": True, "message": result.get('output', '操作成功')})
        else:
            logger.log_api_call('/api/action', 'POST', api_params, "failed", result['message'])
            return jsonify({"success": False, "message": result.get('message', '操作失败')}), 400


# --- 文件管理 API ---
@app.route('/api/files/list', methods=['POST'])
@login_required
def api_list_files():
    data = request.get_json()
    path = data.get('path', '')
    logger.log_api_call('/api/files/list', 'POST', {'path': path})
    result = run_script(['list_files', path])
    if not result['success']:
        return jsonify({"success": False, "error": result['message']}), 500
    try:
        return jsonify(json.loads(result['output']))
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": f"无法解析文件列表: {result['output']}"}), 500


@app.route('/api/files/get_content', methods=['POST'])
@login_required
def api_get_file_content():
    data = request.get_json()
    path = data.get('path')
    if not path: return jsonify({"success": False, "error": "缺少路径"}), 400
    logger.log_api_call('/api/files/get_content', 'POST', {'path': path})
    
    result = run_script(['get_file_content', path])
    if result['success']:
        return Response(result['output'], mimetype='text/plain')
    else:
        return Response(f"读取文件失败: {result['message']}", status=500, mimetype='text/plain')


@app.route('/api/files/save_content', methods=['POST'])
@login_required
def api_save_file_content():
    data = request.get_json()
    path = data.get('path')
    content = data.get('content')
    if not path or content is None: return jsonify({"success": False, "error": "缺少参数"}), 400
    logger.log_api_call('/api/files/save_content', 'POST', {'path': path})
    result = run_script(['save_file_content', path], payload_stdin=content)
    return jsonify(result)

@app.route('/api/files/delete', methods=['POST'])
@login_required
def api_delete_path():
    data = request.get_json()
    path = data.get('path')
    if not path: return jsonify({"success": False, "error": "缺少路径"}), 400
    logger.log_api_call('/api/files/delete', 'POST', {'path': path})
    result = run_script(['delete_path', path])
    return jsonify(result)

@app.route('/api/files/create_folder', methods=['POST'])
@login_required
def api_create_folder():
    data = request.get_json()
    path = data.get('path')
    if not path: return jsonify({"success": False, "error": "缺少路径"}), 400
    logger.log_api_call('/api/files/create_folder', 'POST', {'path': path})
    result = run_script(['create_folder', path])
    return jsonify(result)

@app.route('/api/files/unzip', methods=['POST'])
@login_required
def api_unzip_file():
    data = request.get_json()
    path = data.get('path')
    if not path: return jsonify({"success": False, "error": "缺少路径"}), 400
    logger.log_api_call('/api/files/unzip', 'POST', {'path': path})
    result = run_script(['unzip_file', path])
    return jsonify(result)

@app.route('/api/files/upload', methods=['POST'])
@login_required
def api_upload_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有文件部分"}), 400

    # 检查是否有文件被上传
    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({"success": False, "error": "没有选择文件"}), 400
    
    current_path = request.form.get('path', '')
    if '..' in current_path or current_path.startswith('/'):
        return jsonify({"success": False, "error": "无效的上传路径"}), 400

    uploaded_files = []
    for file in files:
        if file and file.filename:
            filename = file.filename 
            if '/' in filename or '\\' in filename:
                logger.log_api_call('/api/files/upload', 'POST', {'path': current_path, 'filename': filename}, 'failed', '文件名包含路径分隔符')
                continue # 跳过无效文件

            destination_folder = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
            os.makedirs(destination_folder, exist_ok=True)
            
            file.save(os.path.join(destination_folder, filename))
            uploaded_files.append(filename)
            logger.log_api_call('/api/files/upload', 'POST', {'path': current_path, 'filename': filename})

    if not uploaded_files:
         return jsonify({"success": False, "error": "没有成功上传的文件"}), 400

    return jsonify({"success": True, "message": f"成功上传 {len(uploaded_files)} 个文件"})

# --- 日志管理API ---
@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    try:
        limit = int(request.args.get('limit', 100))
        action_filter = request.args.get('action')
        logs = logger.get_logs(limit=limit, action_filter=action_filter)
        logger.log_api_call('/api/logs', 'GET', {'limit': limit, 'action_filter': action_filter})
        return jsonify({"success": True, "logs": logs, "total": len(logs)})
    except Exception as e:
        error_message = f"获取日志失败: {str(e)}"
        logger.log_api_call('/api/logs', 'GET', {}, "failed", error_message)
        return jsonify({"success": False, "message": error_message}), 500

@app.route('/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    try:
        logger.clear_logs()
        return jsonify({"success": True, "message": "日志已清空"})
    except Exception as e:
        error_message = f"清空日志失败: {str(e)}"
        return jsonify({"success": False, "message": error_message}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)