"""状态存储模块 - 用于持久化监控数据"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger


class StateStore:
    """状态存储类 - 使用 JSON 文件存储最近的数据"""
    
    def __init__(self, filename: str = "state_store.json", max_history_minutes: int = 60):
        """
        初始化状态存储
        
        Args:
            filename: 存储文件名
            max_history_minutes: 保留历史数据的时间（分钟）
        """
        self.filename = Path(filename)
        self.max_history_minutes = max_history_minutes
        self.state: Dict[str, Any] = {}
        self.load_state()
    
    def load_state(self) -> None:
        """从文件加载状态"""
        if self.filename.exists():
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                logger.info(f"从 {self.filename} 加载状态成功")
            except Exception as e:
                logger.error(f"加载状态文件失败: {e}")
                self.state = {}
        else:
            logger.info(f"状态文件不存在，创建新文件: {self.filename}")
            self.state = {}
    
    def save_state(self) -> None:
        """保存状态到文件"""
        try:
            # 清理过期数据
            self._cleanup_old_data()
            
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    def _cleanup_old_data(self) -> None:
        """清理过期的历史数据"""
        current_time = time.time()
        cutoff_time = current_time - (self.max_history_minutes * 60)
        
        for key in list(self.state.keys()):
            if key.startswith("_") or key == "last_alert_times":
                continue
            
            data = self.state[key]
            
            # 如果是历史记录列表，清理过期项
            if isinstance(data, dict) and "history" in data:
                history = data["history"]
                if isinstance(history, list):
                    data["history"] = [
                        item for item in history
                        if item.get("timestamp", 0) >= cutoff_time
                    ]
                    # 如果历史为空，且没有最新值，删除整个 key
                    if not data["history"] and "latest" not in data:
                        del self.state[key]
            elif isinstance(data, dict) and "timestamp" in data:
                # 单条记录，检查是否过期
                if data.get("timestamp", 0) < cutoff_time:
                    del self.state[key]
    
    def get_latest(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取指定 key 的最新数据
        
        Args:
            key: 数据键
            
        Returns:
            最新数据字典，包含 value 和 timestamp，不存在返回 None
        """
        data = self.state.get(key)
        
        if data is None:
            return None
        
        # 如果有历史记录，返回最新的
        if isinstance(data, dict) and "history" in data:
            history = data.get("history", [])
            if history:
                latest = sorted(history, key=lambda x: x.get("timestamp", 0))[-1]
                return {
                    "value": latest.get("value"),
                    "timestamp": latest.get("timestamp")
                }
        
        # 直接存储的格式
        if isinstance(data, dict) and "value" in data and "timestamp" in data:
            return data
        
        return None
    
    def get_history(self, key: str, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        获取指定 key 的历史数据（最近 N 分钟）
        
        Args:
            key: 数据键
            minutes: 时间范围（分钟）
            
        Returns:
            历史数据列表
        """
        data = self.state.get(key)
        
        if data is None:
            return []
        
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)
        
        # 如果是历史记录格式
        if isinstance(data, dict) and "history" in data:
            history = data.get("history", [])
            return [
                item for item in history
                if item.get("timestamp", 0) >= cutoff_time
            ]
        
        # 单条记录
        if isinstance(data, dict) and "timestamp" in data:
            if data.get("timestamp", 0) >= cutoff_time:
                return [data]
        
        return []
    
    def get_value_at_time(self, key: str, target_time: float) -> Optional[Any]:
        """
        获取指定时间点的数据（最接近的）
        
        Args:
            key: 数据键
            target_time: 目标时间戳
            
        Returns:
            最接近时间点的数据值
        """
        history = self.get_history(key, minutes=self.max_history_minutes)
        
        if not history:
            return None
        
        # 找到最接近目标时间的记录
        closest = min(history, key=lambda x: abs(x.get("timestamp", 0) - target_time))
        return closest.get("value")
    
    def set(self, key: str, value: Any, timestamp: Optional[float] = None) -> None:
        """
        设置数据值
        
        Args:
            key: 数据键
            value: 数据值
            timestamp: 时间戳（默认当前时间）
        """
        if timestamp is None:
            timestamp = time.time()
        
        # 如果是第一次设置，初始化结构
        if key not in self.state:
            self.state[key] = {
                "latest": {"value": value, "timestamp": timestamp},
                "history": [{"value": value, "timestamp": timestamp}]
            }
        else:
            # 更新最新值
            if isinstance(self.state[key], dict):
                self.state[key]["latest"] = {"value": value, "timestamp": timestamp}
                # 添加到历史记录（去重：如果时间戳相同则更新）
                history = self.state[key].get("history", [])
                # 移除相同时间戳的记录（如果有）
                history = [h for h in history if abs(h.get("timestamp", 0) - timestamp) > 1]
                history.append({"value": value, "timestamp": timestamp})
                # 按时间戳排序
                history.sort(key=lambda x: x.get("timestamp", 0))
                self.state[key]["history"] = history
            else:
                # 旧格式，转换为新格式
                self.state[key] = {
                    "latest": {"value": value, "timestamp": timestamp},
                    "history": [{"value": value, "timestamp": timestamp}]
                }
        
        self.save_state()
    
    def get_last_alert_time(self, alert_key: str) -> Optional[float]:
        """
        获取上次告警时间
        
        Args:
            alert_key: 告警键
            
        Returns:
            上次告警时间戳，不存在返回 None
        """
        if "last_alert_times" not in self.state:
            return None
        return self.state["last_alert_times"].get(alert_key)
    
    def set_last_alert_time(self, alert_key: str, timestamp: Optional[float] = None) -> None:
        """
        设置上次告警时间
        
        Args:
            alert_key: 告警键
            timestamp: 时间戳（默认当前时间）
        """
        if timestamp is None:
            timestamp = time.time()
        
        if "last_alert_times" not in self.state:
            self.state["last_alert_times"] = {}
        
        self.state["last_alert_times"][alert_key] = timestamp
        self.save_state()

