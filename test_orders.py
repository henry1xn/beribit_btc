"""测试脚本 - 查看账户所有挂单（不分币种）"""
import os
import sys
import json
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime

# 加载 .env 文件
load_dotenv()

# 导入项目模块
from config import load_config
from deribit_client import DeribitClient

# 配置日志
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


def test_get_all_orders():
    """测试获取所有挂单和交易信息（不分币种）"""
    
    logger.info("=" * 80)
    logger.info("Deribit 挂单和交易测试工具 - 查看所有信息（不分币种）")
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
        
        # 获取所有币种的挂单
        currencies = ["BTC", "ETH", "USDC", "USDT"]  # 常见的币种
        all_orders = []
        
        logger.info("-" * 80)
        logger.info("第一部分: 获取所有币种的挂单")
        logger.info("-" * 80)
        logger.info("")
        
        method_name = "private/get_open_orders_by_currency"
        
        for currency in currencies:
            logger.info(f"正在获取 {currency} 挂单...")
            params = {"currency": currency}
            
            result = client._make_request(method_name, params=params)
            
            if result is not None:
                if isinstance(result, list):
                    count = len(result)
                    logger.info(f"  ✓ {currency}: {count} 个挂单")
                    all_orders.extend(result)
                elif isinstance(result, dict):
                    logger.info(f"  ✓ {currency}: 1 个挂单（字典格式）")
                    all_orders.append(result)
                else:
                    logger.warning(f"  ✗ {currency}: 返回格式异常 - {type(result)}")
            else:
                logger.info(f"  - {currency}: 没有挂单或 API 返回 None")
        
        logger.info("")
        
        # 获取所有币种的交易历史
        logger.info("-" * 80)
        logger.info("第二部分: 获取所有币种的交易历史（最近 50 笔）")
        logger.info("-" * 80)
        logger.info("")
        
        all_trades = []
        method_name_trades = "private/get_user_trades_by_currency"
        
        for currency in currencies:
            logger.info(f"正在获取 {currency} 交易历史...")
            params = {
                "currency": currency,
                "count": 50,  # 获取最近 50 笔交易
                "include_old": True  # 包含历史交易
            }
            
            try:
                result = client._make_request(method_name_trades, params=params)
                
                if result is not None:
                    # Deribit API 返回格式可能是字典或列表
                    if isinstance(result, dict):
                        if "trades" in result:
                            trades = result["trades"]
                        elif "result" in result:
                            trades = result["result"]
                        else:
                            trades = [result]
                    elif isinstance(result, list):
                        trades = result
                    else:
                        trades = []
                    
                    count = len(trades) if isinstance(trades, list) else 0
                    logger.info(f"  ✓ {currency}: {count} 笔交易")
                    
                    if isinstance(trades, list):
                        all_trades.extend(trades)
                else:
                    logger.info(f"  - {currency}: 没有交易历史或 API 返回 None")
            except Exception as e:
                logger.warning(f"  ✗ {currency}: 获取交易失败 - {e}")
        
        logger.info("")
        
        # 汇总统计
        logger.info("=" * 80)
        logger.info("汇总统计")
        logger.info("=" * 80)
        logger.info(f"总挂单数: {len(all_orders)}")
        logger.info(f"总交易数: {len(all_trades)}")
        logger.info("")
        
        # 显示所有挂单
        if len(all_orders) == 0:
            logger.warning("⚠️  没有找到任何挂单！")
            logger.info("")
            logger.info("可能的原因：")
            logger.info("  1. 账户确实没有挂单")
            logger.info("  2. API 权限不足（需要读取订单的权限）")
            logger.info("  3. API 调用失败（查看上面的错误信息）")
        else:
            # 详细显示所有挂单
            logger.info("-" * 80)
            logger.info("详细挂单信息:")
            logger.info("-" * 80)
            
            # 按币种分组
            orders_by_currency = {}
            orders_by_kind = {}
            
            for i, order in enumerate(all_orders, 1):
                currency = order.get("currency", "unknown")
                kind = order.get("kind", "unknown")
                instrument = order.get("instrument_name", "unknown")
                direction = order.get("direction", "unknown").upper()
                price = order.get("price", 0)
                amount = order.get("amount", 0)
                filled = order.get("filled_amount", 0)
                remaining = amount - filled
                order_type = order.get("order_type", "unknown")
                order_state = order.get("order_state", "unknown")
                
                # 统计
                if currency not in orders_by_currency:
                    orders_by_currency[currency] = []
                orders_by_currency[currency].append(order)
                
                if kind not in orders_by_kind:
                    orders_by_kind[kind] = []
                orders_by_kind[kind].append(order)
                
                # 格式化时间
                creation_ts = order.get("creation_timestamp", 0)
                if creation_ts > 1000000000000:  # 毫秒
                    creation_time = datetime.fromtimestamp(creation_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
                elif creation_ts > 0:  # 秒
                    creation_time = datetime.fromtimestamp(creation_ts).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    creation_time = "N/A"
                
                fill_pct = (filled / amount * 100) if amount > 0 else 0
                
                logger.info(f"\n[{i}] 挂单详情:")
                logger.info(f"  订单ID: {order.get('order_id', 'N/A')}")
                logger.info(f"  合约: {instrument}")
                logger.info(f"  币种: {currency} | 类型: {kind}")
                logger.info(f"  方向: {direction} | 价格: {price:.2f}")
                logger.info(f"  数量: {amount:.4f} | 已成交: {filled:.4f} | 剩余: {remaining:.4f} ({fill_pct:.1f}%)")
                logger.info(f"  订单类型: {order_type} | 状态: {order_state}")
                logger.info(f"  创建时间: {creation_time}")
                
                # 只在 DEBUG 模式下输出完整 JSON
                if config.get("general", {}).get("log_level", "INFO").upper() == "DEBUG":
                    logger.info(f"  原始数据: {json.dumps(order, indent=2, ensure_ascii=False)}")
            
            logger.info("")
            logger.info("-" * 80)
            logger.info("挂单统计信息:")
            logger.info("-" * 80)
            logger.info(f"按币种分组:")
            for currency, orders in orders_by_currency.items():
                logger.info(f"  {currency}: {len(orders)} 个挂单")
            
            logger.info(f"\n按合约类型分组:")
            for kind, orders in orders_by_kind.items():
                logger.info(f"  {kind}: {len(orders)} 个挂单")
            
            logger.info("")
        
        # 显示所有交易
        if len(all_trades) > 0:
            logger.info("=" * 80)
            logger.info(f"交易历史详情（最近 {len(all_trades)} 笔）")
            logger.info("=" * 80)
            logger.info("")
            
            # 按币种和类型分组
            trades_by_currency = {}
            trades_by_kind = {}
            
            # 按时间排序（最新的在前）
            all_trades_sorted = sorted(
                all_trades,
                key=lambda x: x.get("timestamp", 0) or x.get("trade_timestamp", 0),
                reverse=True
            )
            
            # 只显示最近 20 笔交易的详细信息
            display_count = min(20, len(all_trades_sorted))
            logger.info(f"显示最近 {display_count} 笔交易的详细信息：")
            logger.info("-" * 80)
            
            for i, trade in enumerate(all_trades_sorted[:display_count], 1):
                instrument = trade.get("instrument_name", "unknown")
                currency = trade.get("currency", "unknown")
                kind = trade.get("kind", "unknown")
                direction = trade.get("direction", "unknown").upper()
                price = trade.get("price", 0)
                amount = trade.get("amount", 0) or trade.get("quantity", 0)
                fee = trade.get("fee", 0)
                trade_type = trade.get("trade_type", "unknown") or trade.get("order_type", "unknown")
                
                # 格式化时间
                trade_ts = trade.get("timestamp", 0) or trade.get("trade_timestamp", 0)
                if trade_ts > 1000000000000:  # 毫秒
                    trade_time = datetime.fromtimestamp(trade_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
                elif trade_ts > 0:  # 秒
                    trade_time = datetime.fromtimestamp(trade_ts).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    trade_time = "N/A"
                
                # 统计
                if currency not in trades_by_currency:
                    trades_by_currency[currency] = []
                trades_by_currency[currency].append(trade)
                
                if kind not in trades_by_kind:
                    trades_by_kind[kind] = []
                trades_by_kind[kind].append(trade)
                
                logger.info(f"\n[{i}] 交易详情:")
                logger.info(f"  交易ID: {trade.get('trade_id', trade.get('trade_seq', 'N/A'))}")
                logger.info(f"  合约: {instrument}")
                logger.info(f"  币种: {currency} | 类型: {kind}")
                logger.info(f"  方向: {direction} | 价格: {price:.2f} | 数量: {amount:.4f}")
                logger.info(f"  手续费: {fee:.8f} | 交易类型: {trade_type}")
                logger.info(f"  时间: {trade_time}")
            
            if len(all_trades_sorted) > display_count:
                logger.info(f"\n... 还有 {len(all_trades_sorted) - display_count} 笔交易未显示")
            
            logger.info("")
            logger.info("-" * 80)
            logger.info("交易统计信息:")
            logger.info("-" * 80)
            logger.info(f"按币种分组:")
            for currency, trades in trades_by_currency.items():
                logger.info(f"  {currency}: {len(trades)} 笔交易")
            
            logger.info(f"\n按合约类型分组:")
            for kind, trades in trades_by_kind.items():
                logger.info(f"  {kind}: {len(trades)} 笔交易")
        else:
            logger.info("没有交易历史记录")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("测试完成！")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    return True


if __name__ == "__main__":
    success = test_get_all_orders()
    sys.exit(0 if success else 1)

