"""飞书 Webhook 告警通知模块"""
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger


def send_feishu_alert(
    title: str,
    message: str,
    webhook_url: str,
    detail: Optional[Dict[str, Any]] = None
) -> bool:
    """
    发送飞书告警消息
    
    Args:
        title: 告警标题
        message: 告警消息内容
        webhook_url: 飞书 Webhook URL
        detail: 详细信息字典（可选）
        
    Returns:
        是否发送成功
    """
    if not webhook_url:
        logger.warning("飞书 Webhook URL 未配置，跳过发送")
        return False
    
    try:
        # 构建消息文本
        full_message = f"{title}\n\n{message}"
        
        if detail:
            full_message += "\n\n详细信息："
            for key, value in detail.items():
                full_message += f"\n{key}: {value}"
        
        # 飞书 Webhook 标准格式（文本消息）
        payload = {
            "msg_type": "text",
            "content": {
                "text": full_message
            }
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                logger.info(f"飞书告警发送成功: {title}")
                return True
            else:
                logger.error(f"飞书告警发送失败: {result.get('msg', '未知错误')}")
                return False
        else:
            logger.error(f"飞书告警 HTTP 错误 {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("发送飞书告警超时")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"发送飞书告警异常: {e}")
        return False
    except Exception as e:
        logger.error(f"发送飞书告警时发生未知错误: {e}")
        return False


def format_option_alert(
    instrument_name: str,
    metric_type: str,  # "IV" 或 "Gamma"
    current_value: float,
    previous_value: float,
    pct_change: float,
    abs_change: float,
    direction: str = "buy",
    size: float = 0
) -> tuple[str, str]:
    """
    格式化期权告警消息
    
    Returns:
        (title, message) 元组
    """
    title = f"[Deribit BTC 期权 {metric_type} 异动告警]"
    
    # 计算变化方向和百分比
    change_sign = "+" if pct_change >= 0 else ""
    abs_sign = "+" if abs_change >= 0 else ""
    
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    message = f"""合约: {instrument_name}
方向: {direction.upper()}
持仓量: {size}

当前 {metric_type}: {current_value:.6f}
5 分钟前 {metric_type}: {previous_value:.6f}
5 分钟变化: {change_sign}{pct_change*100:.2f}% ({abs_sign}{abs_change:.6f})

触发条件: 5 分钟内变化超过阈值
时间: {current_time}"""
    
    return title, message


def format_dvol_alert(
    current_dvol: float,
    previous_dvol: float,
    pct_change: float,
    abs_change: float,
    iv_percentile: Optional[float] = None
) -> tuple[str, str]:
    """
    格式化 DVOL 告警消息
    
    Returns:
        (title, message) 元组
    """
    title = f"[Deribit BTC DVOL 异动告警]"
    
    change_sign = "+" if pct_change >= 0 else ""
    abs_sign = "+" if abs_change >= 0 else ""
    
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    message = f"""当前 DVOL: {current_dvol:.2f}
5 分钟前 DVOL: {previous_dvol:.2f}
5 分钟变化: {change_sign}{pct_change*100:.2f}% ({abs_sign}{abs_change:.2f})"""
    
    if iv_percentile is not None:
        message += f"\n当前 IV 百分位: {iv_percentile*100:.1f}%"
    
    message += f"\n\n触发条件: 5 分钟内变化超过阈值\n时间: {current_time}"
    
    return title, message


def format_dvol_percentile_alert(
    current_percentile: float,
    previous_percentile: float,
    pct_change: float,
    abs_change: float,
    current_dvol: float
) -> tuple[str, str]:
    """
    格式化 DVOL IV 百分位告警消息
    
    Returns:
        (title, message) 元组
    """
    title = f"[Deribit BTC DVOL IV 百分位异动告警]"
    
    change_sign = "+" if pct_change >= 0 else ""
    abs_sign = "+" if abs_change >= 0 else ""
    
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    message = f"""当前 DVOL: {current_dvol:.2f}
当前 IV 百分位: {current_percentile*100:.1f}%
5 分钟前 IV 百分位: {previous_percentile*100:.1f}%
5 分钟变化: {change_sign}{pct_change*100:.2f}% ({abs_sign}{abs_change*100:.1f} 百分点)

触发条件: 5 分钟内 IV 百分位变化超过阈值
时间: {current_time}"""
    
    return title, message

