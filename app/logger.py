import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from flask import request, session

class L4D2Logger:
    """L4D2服务器管理面板日志记录器"""
    
    def __init__(self, log_file_path: str = "./logs/server_operations.json"):
        self.log_file_path = log_file_path
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """确保日志目录存在"""
        log_dir = os.path.dirname(self.log_file_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def _get_user_info(self) -> Dict[str, Any]:
        """获取当前用户信息"""
        user_info = {
            "ip_address": request.remote_addr if request else "unknown",
            "user_agent": request.headers.get('User-Agent', 'unknown') if request else "unknown",
            "logged_in": session.get('logged_in', False) if session else False
        }
        return user_info
    
    def _create_log_entry(self, action: str, details: Dict[str, Any], 
                         status: str = "success", error_message: Optional[str] = None) -> Dict[str, Any]:
        """创建日志条目"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details,
            "user_info": self._get_user_info()
        }
        
        if error_message:
            log_entry["error_message"] = error_message
        
        return log_entry
    
    def _write_log(self, log_entry: Dict[str, Any]):
        """写入日志到文件"""
        try:
            # 读取现有日志
            logs = []
            if os.path.exists(self.log_file_path):
                try:
                    with open(self.log_file_path, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    logs = []
            
            # 添加新日志条目
            logs.append(log_entry)
            
            # 保持最近1000条日志记录
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # 写入文件
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            # 如果日志写入失败，至少打印到控制台
            print(f"日志写入失败: {e}")
            print(f"日志内容: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_action(self, action: str, details: Dict[str, Any], 
                   status: str = "success", error_message: Optional[str] = None):
        """记录操作日志"""
        log_entry = self._create_log_entry(action, details, status, error_message)
        self._write_log(log_entry)
    
    def log_login_attempt(self, username: str, success: bool, ip_address: str = None):
        """记录登录尝试"""
        details = {
            "username": username,
            "ip_address": ip_address or (request.remote_addr if request else "unknown")
        }
        status = "success" if success else "failed"
        error_message = None if success else "用户名或密码错误"
        
        self.log_action("login_attempt", details, status, error_message)
    
    def log_logout(self):
        """记录登出"""
        details = {}
        self.log_action("logout", details)
    
    def log_api_call(self, endpoint: str, method: str, params: Dict[str, Any] = None, 
                     response_status: str = "success", error_message: Optional[str] = None):
        """记录API调用"""
        details = {
            "endpoint": endpoint,
            "method": method,
            "params": params or {}
        }
        self.log_action("api_call", details, response_status, error_message)
    
    def log_script_execution(self, script_args: list, success: bool, 
                           output: str = None, error_message: str = None):
        """记录脚本执行"""
        details = {
            "script_args": script_args,
            "output_preview": output[:200] if output else None  # 只记录前200个字符
        }
        status = "success" if success else "failed"
        self.log_action("script_execution", details, status, error_message)
    
    def get_logs(self, limit: int = 100, action_filter: str = None) -> list:
        """获取日志记录"""
        try:
            if not os.path.exists(self.log_file_path):
                return []
            
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 按时间倒序排列
            logs.reverse()
            
            # 过滤特定操作
            if action_filter:
                logs = [log for log in logs if log.get('action') == action_filter]
            
            # 限制返回数量
            return logs[:limit]
        
        except Exception as e:
            print(f"读取日志失败: {e}")
            return []
    
    def clear_logs(self):
        """清空日志"""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            self.log_action("clear_logs", {"message": "日志已清空"})
        except Exception as e:
            print(f"清空日志失败: {e}")

# 全局日志实例
logger = L4D2Logger()