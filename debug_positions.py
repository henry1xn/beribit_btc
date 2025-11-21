"""调试脚本 - 查看期权持仓的原始数据"""
import os
import sys
import json
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件
load_dotenv()

# 导入项目模块
from config import load_config
from deribit_client import DeribitClient

# 配置日志
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    level="DEBUG",  # 使用 DEBUG 级别查看详细信息
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


def debug_positions():
    """调试期权持仓数据"""
    
    logger.info("=" * 80)
    logger.info("期权持仓数据调试工具")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        # 加载配置
        config = load_config()
        deribit_config = config.get("deribit", {})
        
        # 创建 Deribit 客户端
        logger.info("正在连接 Deribit API...")
        client = DeribitClient(
            client_id=deribit_config.get("client_id", ""),
            client_secret=deribit_config.get("client_secret", ""),
            base_url=deribit_config.get("base_url", "https://www.deribit.com")
        )
        
        logger.info("认证成功！")
        logger.info("")
        
        # 获取 BTC 和 USDC 的期权持仓
        currencies = ["BTC", "USDC"]
        
        for currency in currencies:
            logger.info("-" * 80)
            logger.info(f"获取 {currency} 期权持仓...")
            logger.info("-" * 80)
            
            method_name = "private/get_positions"
            params = {
                "currency": currency,
                "kind": "option"
            }
            
            result = client._make_request(method_name, params=params)
            
            if result is None:
                logger.warning(f"{currency} 期权持仓: API 返回 None")
                continue
            
            if not isinstance(result, list):
                result = [result]
            
            logger.info(f"{currency} 期权持仓数量: {len(result)}")
            logger.info("")
            
            # 只显示 BTC 相关的合约
            btc_positions = [pos for pos in result if "BTC" in pos.get("instrument_name", "").upper()]
            
            if not btc_positions:
                logger.info(f"{currency} 中没有 BTC 相关的期权持仓")
                continue
            
            logger.info(f"{currency} 中 BTC 相关的期权持仓数量: {len(btc_positions)}")
            logger.info("")
            
            # 显示每个持仓的详细信息
            for i, pos in enumerate(btc_positions, 1):
                logger.info(f"\n[{i}] 持仓详情:")
                logger.info(f"  合约名称: {pos.get('instrument_name', 'N/A')}")
                logger.info(f"  持仓量: {pos.get('size', 0)}")
                logger.info(f"  方向: {pos.get('size', 0) > 0 and 'BUY' or 'SELL'}")
                logger.info("")
                logger.info("  原始数据（完整 JSON）:")
                logger.info(json.dumps(pos, indent=2, ensure_ascii=False))
                logger.info("")
                logger.info("  Greeks 数据:")
                greeks = pos.get("greeks", {})
                if greeks:
                    logger.info(json.dumps(greeks, indent=2, ensure_ascii=False))
                else:
                    logger.warning("  Greeks 数据为空或不存在")
                logger.info("")
                logger.info("  提取的关键字段:")
                logger.info(f"    mark_iv: {pos.get('mark_iv', 'N/A')}")
                logger.info(f"    greeks.gamma: {greeks.get('gamma', 'N/A') if greeks else 'N/A'}")
                logger.info(f"    greeks.delta: {greeks.get('delta', 'N/A') if greeks else 'N/A'}")
                logger.info(f"    greeks.theta: {greeks.get('theta', 'N/A') if greeks else 'N/A'}")
                logger.info(f"    greeks.vega: {greeks.get('vega', 'N/A') if greeks else 'N/A'}")
                logger.info("")
                logger.info("  所有可用字段:")
                for key, value in pos.items():
                    if key != "greeks":  # greeks 已经单独显示
                        logger.info(f"    {key}: {value}")
                logger.info("-" * 80)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("调试完成！")
        logger.info("=" * 80)
        logger.info("")
        logger.info("提示:")
        logger.info("  1. 查看上面的 '原始数据（完整 JSON）' 了解 API 返回的完整结构")
        logger.info("  2. 查看 'Greeks 数据' 了解 Gamma 等字段的实际位置")
        logger.info("  3. 如果 Gamma 为 0，检查是否有其他字段名（如 'gamma_total', 'total_gamma' 等）")
        
    except Exception as e:
        logger.error(f"调试过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    return True


if __name__ == "__main__":
    success = debug_positions()
    sys.exit(0 if success else 1)

