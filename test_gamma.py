"""测试脚本 - 专门抓取 Gamma 值"""
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
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


def test_gamma():
    """测试抓取 Gamma 值"""
    
    target_instrument = "BTC_USDC-23NOV25-81000-P"
    
    logger.info("=" * 80)
    logger.info(f"Gamma 值测试工具 - 合约: {target_instrument}")
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
        
        # 方法1: 使用 public/get_order_book API
        logger.info("=" * 80)
        logger.info("方法1: 使用 public/get_order_book API")
        logger.info("=" * 80)
        logger.info("")
        
        method_name = "public/get_order_book"
        params = {
            "instrument_name": target_instrument,
            "depth": 1  # 只获取第一层
        }
        
        logger.info(f"正在获取合约信息: {target_instrument}...")
        result_orderbook = client._make_request(method_name, params=params)
        
        if result_orderbook is None:
            logger.warning(f"⚠️  get_order_book API 返回 None")
        else:
            logger.info("✓ get_order_book API 调用成功")
            logger.info("")
            logger.info("-" * 80)
            logger.info("get_order_book API 返回的完整数据:")
            logger.info("-" * 80)
            logger.info(json.dumps(result_orderbook, indent=2, ensure_ascii=False))
            logger.info("")
            
            # 提取可能的 Greeks 字段
            logger.info("-" * 80)
            logger.info("从 get_order_book 提取的 Greeks 相关字段:")
            logger.info("-" * 80)
            
            # 检查所有可能的字段
            for key in ["greeks", "greek", "gamma", "delta", "theta", "vega", "mark_iv", "iv", "mark_price"]:
                if key in result_orderbook:
                    logger.info(f"  {key}: {result_orderbook.get(key)}")
            
            # 检查 greeks 字段
            if "greeks" in result_orderbook:
                greeks_orderbook = result_orderbook.get("greeks")
                logger.info("")
                logger.info("greeks 字段内容:")
                if isinstance(greeks_orderbook, dict):
                    logger.info(json.dumps(greeks_orderbook, indent=2, ensure_ascii=False))
                    if "gamma" in greeks_orderbook:
                        logger.info(f"")
                        logger.info(f"✓ 找到 Gamma: {greeks_orderbook.get('gamma')}")
                else:
                    logger.info(f"  greeks 类型: {type(greeks_orderbook)}, 值: {greeks_orderbook}")
        
        logger.info("")
        logger.info("=" * 80)
        
        # 方法2: 使用 private/get_positions API（如果有持仓）
        logger.info("方法2: 使用 private/get_positions API（持仓信息）")
        logger.info("=" * 80)
        logger.info("")
        
        # 从多个币种获取持仓
        currencies = ["BTC", "USDC", "ETH"]
        all_positions_raw = []
        
        for currency in currencies:
            logger.info(f"正在获取 {currency} 期权持仓...")
            method_name = "private/get_positions"
            params = {
                "currency": currency,
                "kind": "option"
            }
            
            result = client._make_request(method_name, params=params)
            
            if result is None:
                logger.info(f"  {currency}: API 返回 None")
                continue
            
            if not isinstance(result, list):
                result = [result]
            
            logger.info(f"  {currency}: 获取到 {len(result)} 个持仓记录")
            all_positions_raw.extend(result)
        
        logger.info("")
        logger.info(f"总共获取到 {len(all_positions_raw)} 个持仓记录")
        logger.info("")
        
        # 查找目标合约
        target_position = None
        for pos in all_positions_raw:
            if pos.get("instrument_name", "") == target_instrument:
                target_position = pos
                break
        
        if target_position:
            logger.info("=" * 80)
            logger.info(f"从持仓中找到目标合约: {target_instrument}")
            logger.info("=" * 80)
            logger.info("")
            
            # 输出完整的原始数据
            logger.info("-" * 80)
            logger.info("持仓 API 返回的完整数据 (JSON):")
            logger.info("-" * 80)
            logger.info(json.dumps(target_position, indent=2, ensure_ascii=False))
            logger.info("")
            
            # 提取关键信息
            size = float(target_position.get("size", 0))
            greeks = target_position.get("greeks", {})
        else:
            logger.info(f"⚠️  持仓中未找到合约: {target_instrument}（可能没有持仓）")
            logger.info("")
            logger.info("当前所有持仓的合约名称:")
            for i, pos in enumerate(all_positions_raw, 1):
                instrument = pos.get("instrument_name", "unknown")
                size = pos.get("size", 0)
                if abs(size) > 1e-8:  # 只显示有效持仓
                    logger.info(f"  [{i}] {instrument} (size={size})")
            
            # 如果没有持仓，使用 order_book 的结果
            logger.info("")
            logger.info("=" * 80)
            logger.info("由于没有持仓，使用 get_order_book API 的结果")
            logger.info("=" * 80)
            logger.info("")
            
            if result_orderbook:
                target_position = result_orderbook
                size = 0  # order_book 没有 size
                greeks = result_orderbook.get("greeks", {})
            else:
                logger.error("❌ 无法获取合约信息！")
                return False
        
        logger.info("-" * 80)
        logger.info("提取的关键字段:")
        logger.info("-" * 80)
        logger.info(f"合约名称: {target_position.get('instrument_name', 'N/A')}")
        logger.info(f"持仓量 (size): {size}")
        logger.info(f"持仓方向: {'做多' if size > 0 else '做空' if size < 0 else '无持仓'}")
        logger.info("")
        
        logger.info("Greeks 数据:")
        if greeks:
            logger.info(json.dumps(greeks, indent=2, ensure_ascii=False))
        else:
            logger.warning("  Greeks 数据为空！")
        logger.info("")
        
        # 输出所有可用字段
        logger.info("-" * 80)
        logger.info("所有可用字段:")
        logger.info("-" * 80)
        for key, value in target_position.items():
            logger.info(f"  {key}: {value}")
        logger.info("")
        
        # 提取 Gamma 相关的所有可能字段
        logger.info("-" * 80)
        logger.info("Gamma 相关字段提取:")
        logger.info("-" * 80)
        
        # 1. 检查 greeks 是否存在
        logger.info(f"greeks 是否存在: {greeks is not None}")
        if greeks:
            logger.info(f"greeks 类型: {type(greeks)}")
            if isinstance(greeks, dict):
                logger.info(f"greeks 字典内容: {greeks}")
                logger.info(f"greeks 字典的所有键: {list(greeks.keys()) if greeks else 'None'}")
            else:
                logger.info(f"greeks 不是字典，而是: {greeks}")
        else:
            logger.warning("  ⚠️  greeks 数据为空或不存在！")
        
        logger.info("")
        
        # 2. 从 greeks 字典中获取
        gamma_from_greeks = None
        if greeks and isinstance(greeks, dict):
            gamma_from_greeks = greeks.get("gamma")
            logger.info(f"greeks.gamma: {gamma_from_greeks}")
        
        # 3. 直接从 position 中获取（可能字段展开）
        gamma_from_pos = target_position.get("gamma")
        logger.info(f"position.gamma: {gamma_from_pos}")
        
        # 4. 尝试其他可能的字段名
        logger.info("")
        logger.info("其他可能的 Gamma 字段:")
        for field in ["gamma_total", "total_gamma", "gamma_pct", "gamma_net", "gamma_position", "gamma_bs", "gamma_black_scholes"]:
            if field in target_position:
                logger.info(f"  position.{field}: {target_position.get(field)}")
            if greeks and isinstance(greeks, dict) and field in greeks:
                logger.info(f"  greeks.{field}: {greeks.get(field)}")
        
        logger.info("")
        
        # 5. 检查持仓量
        logger.info("-" * 80)
        logger.info("持仓信息:")
        logger.info("-" * 80)
        logger.info(f"size: {size}")
        logger.info(f"size 是否不为0: {abs(size) > 1e-8}")
        logger.info("")
        
        # 尝试不同的计算方式
        logger.info("-" * 80)
        logger.info("尝试不同的 Gamma 计算方式:")
        logger.info("-" * 80)
        
        # 使用从 greeks 获取的 Gamma（主要来源）
        # 如果 greeks 中没有，尝试从 position 中获取
        gamma_raw = None
        if gamma_from_greeks is not None:
            gamma_raw = gamma_from_greeks
            logger.info(f"使用 greeks.gamma: {gamma_raw}")
        elif gamma_from_pos is not None:
            gamma_raw = gamma_from_pos
            logger.info(f"使用 position.gamma: {gamma_raw}")
        else:
            logger.warning("⚠️  无法从任何字段中获取 Gamma 值！")
            logger.info("")
            logger.info("请检查上面的输出，确认 Gamma 值是否存在")
            return False
        
        if gamma_raw is not None:
            gamma_raw = float(gamma_from_greeks or 0)
            
            logger.info(f"原始 Gamma (从 greeks.gamma): {gamma_raw}")
            logger.info(f"原始 Gamma 绝对值: {abs(gamma_raw)}")
            logger.info("")
            
            if abs(size) > 1e-8:
                # 方式1: 直接使用原始值（绝对值）
                gamma_method1 = abs(gamma_raw)
                logger.info(f"方式1 - 直接绝对值: {gamma_method1:.8f}")
                
                # 方式2: 除以持仓量（假设原始值是总持仓 Gamma）
                gamma_method2 = abs(gamma_raw) / abs(size)
                logger.info(f"方式2 - 除以 size ({abs(size)}) = {gamma_method2:.8f}")
                
                # 方式3: 乘以持仓量（假设原始值是单个合约 Gamma）
                gamma_method3 = abs(gamma_raw) * abs(size)
                logger.info(f"方式3 - 乘以 size ({abs(size)}) = {gamma_method3:.8f}")
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("判断:")
                logger.info("=" * 80)
                logger.info(f"网页显示的 Gamma: 0.00005 (单个合约)")
                logger.info("")
                logger.info("对比结果:")
                logger.info(f"  方式1 (直接绝对值 {gamma_method1:.8f}): {'✓ 匹配' if abs(gamma_method1 - 0.00005) < 0.000001 else '✗ 不匹配'}")
                logger.info(f"  方式2 (除以size {gamma_method2:.8f}): {'✓ 匹配' if abs(gamma_method2 - 0.00005) < 0.000001 else '✗ 不匹配'}")
                logger.info(f"  方式3 (乘以size {gamma_method3:.8f}): {'✓ 匹配' if abs(gamma_method3 - 0.00005) < 0.000001 else '✗ 不匹配'}")
                logger.info("")
                
                # 推荐使用的值
                if abs(gamma_method1 - 0.00005) < 0.000001:
                    logger.info("✓ 推荐使用: 方式1 (直接绝对值)")
                    logger.info(f"  代码应该使用: gamma = abs(gamma_raw)")
                elif abs(gamma_method2 - 0.00005) < 0.000001:
                    logger.info("✓ 推荐使用: 方式2 (除以 size)")
                    logger.info(f"  代码应该使用: gamma = abs(gamma_raw) / abs(size)")
                elif abs(gamma_method3 - 0.00005) < 0.000001:
                    logger.info("✓ 推荐使用: 方式3 (乘以 size)")
                    logger.info(f"  代码应该使用: gamma = abs(gamma_raw) * abs(size)")
                else:
                    logger.warning("⚠️  没有找到匹配的计算方式，可能需要进一步调试")
                    logger.info("")
                    logger.info("可能的原因:")
                    logger.info("  1. API 返回的 Gamma 值有其他含义")
                    logger.info("  2. 需要查看 API 文档确认 Gamma 的含义")
                    logger.info("  3. 可能需要从其他字段获取 Gamma")
            else:
                logger.warning("⚠️  持仓量为 0，无法测试计算方式")
        else:
            logger.error("❌ 无法从 API 数据中提取 Gamma 值！")
            logger.info("")
            logger.info("请检查:")
            logger.info("  1. 合约是否有持仓（size != 0）")
            logger.info("  2. API 返回的数据结构是否正确")
            logger.info("  3. Greeks 数据是否存在")
        
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
    success = test_gamma()
    sys.exit(0 if success else 1)

