"""配置加载模块"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any
from loguru import logger

# 加载 .env 文件
load_dotenv()


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    加载配置文件并合并环境变量
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        完整的配置字典
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # 从环境变量加载敏感信息
    # 确保 deribit 配置节存在
    if "deribit" not in config:
        config["deribit"] = {}
    
    config["deribit"]["client_id"] = os.getenv("DERIBIT_CLIENT_ID", "")
    config["deribit"]["client_secret"] = os.getenv("DERIBIT_CLIENT_SECRET", "")
    config["deribit"]["base_url"] = os.getenv(
        "DERIBIT_BASE_URL", 
        config.get("deribit", {}).get("base_url", "https://www.deribit.com")
    )
    
    # 确保 feishu 配置节存在
    if "feishu" not in config:
        config["feishu"] = {}
    
    config["feishu"]["webhook_url"] = os.getenv("FEISHU_WEBHOOK_URL", "")
    
    # 验证必要的配置项
    if not config["deribit"]["client_id"] or not config["deribit"]["client_secret"]:
        logger.warning("Deribit 凭证未设置，请检查 .env 文件")
    
    if not config["feishu"]["webhook_url"]:
        logger.warning("飞书 Webhook URL 未设置，告警功能将不可用")
    
    # 设置日志级别
    log_level = config.get("general", {}).get("log_level", "INFO")
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    
    return config

