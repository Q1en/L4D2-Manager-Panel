import os
import subprocess
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response

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
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return jsonify(result.stdout)
    except subprocess.CalledProcessError as e:
        error_message = f"脚本执行失败: {e.stderr}"
        return jsonify({"error": error_message}), 500
    except Exception as e:
        return jsonify({"error": f"未知错误: {str(e)}"}), 500

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
        if request.form.get('username') == PANEL_USER and request.form.get('password') == PANEL_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="用户名或密码错误！")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- 页面路由 ---
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- API 路由 ---
@app.route('/api/status', methods=['GET'])
@login_required
def api_get_status():
    return run_script(['get_status'])

@app.route('/api/instances', methods=['GET'])
@login_required
def api_get_instances():
    return run_script(['get_instances'])

@app.route('/api/plugins', methods=['GET'])
@login_required
def api_get_plugins():
    return run_script(['get_plugins'])

@app.route('/api/action', methods=['POST'])
@login_required
def api_action():
    data = request.get_json()
    action = data.get('action')
    payload = data.get('payload')

    if not action:
        return jsonify({"error": "缺少 'action' 参数"}), 400

    # 对于长时间运行的部署任务，使用流式响应
    if action == 'deploy_server':
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
            process.wait()
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
            return jsonify({"success": True, "message": result.stdout})
        except subprocess.CalledProcessError as e:
            return jsonify({"success": False, "message": e.stderr or e.stdout}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)