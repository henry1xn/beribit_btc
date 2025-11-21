"""监控逻辑核心模块"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from deribit_client import DeribitClient, OptionPosition, DvolData
from state_store import StateStore
from notifier import (
    send_feishu_alert
)


class Monitor:
    """监控器主类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化监控器
        
        Args:
            config: 配置字典
        """
        self.config = config
        
        # 初始化 Deribit 客户端
        deribit_config = config.get("deribit", {})
        self.client = DeribitClient(
            client_id=deribit_config["client_id"],
            client_secret=deribit_config["client_secret"],
            base_url=deribit_config.get("base_url", "https://www.deribit.com")
        )
        
        # 初始化状态存储
        self.state_store = StateStore(max_history_minutes=60)
        
        # 飞书配置
        self.feishu_webhook_url = config.get("feishu", {}).get("webhook_url", "")
        self.enable_alert = config.get("alert", {}).get("enable_alert", True)
        self.cooldown_seconds = config.get("alert", {}).get("cooldown_seconds", 300)
        
        # 监控阈值
        self.option_thresholds = config.get("option_greeks_thresholds", {})
        self.dvol_thresholds = config.get("dvol_thresholds", {})
        
        # Deribit 配置
        self.currency = deribit_config.get("underlying", "BTC")
        
        logger.info("监控器初始化完成")
        logger.info("直接获取所有持仓（不过滤）")
    
    
    def run(self) -> None:
        """执行一次监控循环"""
        try:
            current_time = time.time()
            
            # 1. 获取账户所有期权持仓（直接获取，不过滤）
            # 尝试从主要币种获取持仓
            currencies = ["BTC", "USDC", "ETH", "SOL"]  # 常见币种
            all_positions = []
            
            for currency in currencies:
                positions = self.client.get_account_option_positions(currency=currency)
                all_positions.extend(positions)
            
            if all_positions:
                logger.info(f"获取到 {len(all_positions)} 个期权持仓")
                self._check_positions(all_positions, current_time)
            
            # 2. 获取 DVOL 数据
            dvol_data = self.client.get_btc_dvol()
            if dvol_data:
                self._check_dvol(dvol_data, current_time)
            
        except Exception as e:
            logger.error(f"监控循环执行异常: {e}", exc_info=True)
    
    def _check_positions(self, positions: List[OptionPosition], current_time: float) -> None:
        """
        检查期权持仓的 IV 和 Gamma 异动
        
        Args:
            positions: 期权持仓列表
            current_time: 当前时间戳
        """
        for position in positions:
            instrument_name = position.instrument_name
            
            # 获取历史数据（5 分钟前）
            history_5m = self.state_store.get_history(instrument_name, minutes=5)
            
            if not history_5m:
                # 没有历史数据，直接保存当前值
                logger.info(
                    f"{instrument_name}: Gamma={position.gamma:.8f}, Vega={position.vega:.2f}"
                )
                self.state_store.set(
                    instrument_name,
                    {
                        "gamma": position.gamma,
                        "vega": position.vega,
                        "delta": position.delta,
                        "direction": position.direction,
                        "size": position.size
                    },
                    current_time
                )
                # 检查 Gamma 分阶段预警和 Vega 预警
                self._check_gamma_levels(position, current_time)
                self._check_vega_threshold(position, current_time)
                continue
            
            # 找到 5 分钟前最接近的数据
            target_time = current_time - (5 * 60)
            history_sorted = sorted(history_5m, key=lambda x: abs(x.get("timestamp", 0) - target_time))
            
            if not history_sorted:
                # 保存当前值并继续
                # 输出当前持仓信息（包括 Gamma 和 Vega 绝对数值）
                logger.info(
                    f"{instrument_name}: Gamma={position.gamma:.8f}, Vega={position.vega:.2f}"
                )
                self.state_store.set(
                    instrument_name,
                    {
                        "gamma": position.gamma,
                        "vega": position.vega,
                        "delta": position.delta,
                        "direction": position.direction,
                        "size": position.size
                    },
                    current_time
                )
                # 检查 Gamma 分阶段预警和 Vega 预警
                self._check_gamma_levels(position, current_time)
                self._check_vega_threshold(position, current_time)
                continue
            
            # 不再需要检查 Gamma 5分钟变化，直接输出当前值并检查绝对值阈值
            # 输出当前持仓信息（包括 Gamma 和 Vega 绝对数值）
            logger.info(
                f"{instrument_name}: Gamma={position.gamma:.8f}, Vega={position.vega:.2f}"
            )
            
            # 检查 Gamma 分阶段预警（绝对值阈值）
            self._check_gamma_levels(position, current_time)
            
            # 检查 Vega 预警
            self._check_vega_threshold(position, current_time)
            
            # 保存当前值（保存 Gamma 和 Vega）
            self.state_store.set(
                instrument_name,
                {
                    "gamma": position.gamma,
                    "vega": position.vega,
                    "delta": position.delta,
                    "direction": position.direction,
                    "size": position.size
                },
                current_time
            )
    
    def _check_gamma_levels(self, position: OptionPosition, current_time: float) -> None:
        """
        检查 Gamma 分阶段预警（轻度/中度/重度）
        
        Args:
            position: 期权持仓
            current_time: 当前时间戳
        """
        gamma_value = abs(position.gamma)  # 使用绝对值
        gamma_thresholds = self.option_thresholds.get("gamma", {})
        
        level_1 = gamma_thresholds.get("level_1_light", 0.0001)
        level_2 = gamma_thresholds.get("level_2_medium", 0.0005)
        level_3 = gamma_thresholds.get("level_3_heavy", 0.001)
        
        # 判断当前处于哪个阶段
        alert_level = None
        alert_severity = None
        
        if gamma_value >= level_3:
            alert_level = level_3
            alert_severity = "重度"
        elif gamma_value >= level_2:
            alert_level = level_2
            alert_severity = "中度"
        elif gamma_value >= level_1:
            alert_level = level_1
            alert_severity = "轻度"
        
        if alert_level is not None:
            alert_key = f"{position.instrument_name}_gamma_level_{alert_severity}"
            
            # 检查冷却时间
            if not self._should_alert(alert_key, current_time):
                logger.debug(f"{alert_key} 在冷却期内，跳过告警")
                return
            
            # 发送告警
            if self.enable_alert:
                title = f"🚨 Gamma {alert_severity}预警 - {position.instrument_name}"
                message = (
                    f"合约: {position.instrument_name}\n"
                    f"方向: {position.direction.upper()}\n"
                    f"持仓量: {position.size}\n"
                    f"当前 Gamma: {gamma_value:.8f}\n"
                    f"预警级别: {alert_severity}\n"
                    f"触发阈值: {alert_level:.8f}\n"
                    f"⚠️ Gamma 已达到 {alert_severity}预警水平！"
                )
                
                detail = {
                    "预警级别": alert_severity,
                    "当前 Gamma": f"{gamma_value:.8f}",
                    "触发阈值": f"{alert_level:.8f}"
                }
                
                success = send_feishu_alert(
                    title=title,
                    message=message,
                    webhook_url=self.feishu_webhook_url,
                    detail=detail
                )
                
                if success:
                    self.state_store.set_last_alert_time(alert_key, current_time)
                    logger.warning(f"Gamma {alert_severity}预警已发送: {position.instrument_name} - Gamma={gamma_value:.8f}")
            else:
                logger.info(f"[告警已禁用] Gamma {alert_severity}预警: {position.instrument_name} - Gamma={gamma_value:.8f}")
        
        # 只在触发预警时输出 Gamma 值
    
    def _check_vega_threshold(self, position: OptionPosition, current_time: float) -> None:
        """
        检查 Vega 分阶段预警（轻度/中度/重度）
        
        Args:
            position: 期权持仓
            current_time: 当前时间戳
        """
        vega_value = abs(position.vega)  # 使用绝对值
        vega_thresholds = self.option_thresholds.get("vega", {})
        
        level_1 = vega_thresholds.get("level_1_light", 10.0)
        level_2 = vega_thresholds.get("level_2_medium", 30.0)
        level_3 = vega_thresholds.get("level_3_heavy", 50.0)
        
        # 判断当前处于哪个阶段
        alert_level = None
        alert_severity = None
        
        if vega_value >= level_3:
            alert_level = level_3
            alert_severity = "重度"
        elif vega_value >= level_2:
            alert_level = level_2
            alert_severity = "中度"
        elif vega_value >= level_1:
            alert_level = level_1
            alert_severity = "轻度"
        
        if alert_level is not None:
            alert_key = f"{position.instrument_name}_vega_level_{alert_severity}"
            
            # 检查冷却时间
            if not self._should_alert(alert_key, current_time):
                logger.debug(f"{alert_key} 在冷却期内，跳过告警")
                return
            
            # 发送告警
            if self.enable_alert:
                title = f"🚨 Vega {alert_severity}预警 - {position.instrument_name}"
                message = (
                    f"合约: {position.instrument_name}\n"
                    f"方向: {position.direction.upper()}\n"
                    f"持仓量: {position.size}\n"
                    f"当前 Vega: {vega_value:.2f}\n"
                    f"预警级别: {alert_severity}\n"
                    f"触发阈值: {alert_level:.2f}\n"
                    f"⚠️ Vega 已达到 {alert_severity}预警水平！"
                )
                
                detail = {
                    "预警级别": alert_severity,
                    "当前 Vega": f"{vega_value:.2f}",
                    "触发阈值": f"{alert_level:.2f}"
                }
                
                success = send_feishu_alert(
                    title=title,
                    message=message,
                    webhook_url=self.feishu_webhook_url,
                    detail=detail
                )
                
                if success:
                    self.state_store.set_last_alert_time(alert_key, current_time)
                    logger.warning(f"Vega {alert_severity}预警已发送: {position.instrument_name} - Vega={vega_value:.2f}")
            else:
                logger.info(f"[告警已禁用] Vega {alert_severity}预警: {position.instrument_name} - Vega={vega_value:.2f}")
        
        # 只在触发预警时输出 Vega 值
    
    def _check_dvol(self, dvol_data: DvolData, current_time: float) -> None:
        """
        检查 DVOL 异动
        
        Args:
            dvol_data: DVOL 数据
            current_time: 当前时间戳
        """
        current_dvol = dvol_data.value
        
        # 获取历史数据
        history_5m = self.state_store.get_history("dvol", minutes=5)
        
        if not history_5m:
            # 没有历史数据，直接保存
            logger.info(f"[DVOL 监控] DVOL 首次记录: 当前值={current_dvol:.2f}")
            self.state_store.set("dvol", current_dvol, current_time)
            return
        
        # 找到 5 分钟前最接近的数据
        target_time = current_time - (5 * 60)
        history_sorted = sorted(history_5m, key=lambda x: abs(x.get("timestamp", 0) - target_time))
        
        if not history_sorted:
            self.state_store.set("dvol", current_dvol, current_time)
            return
        
        previous_dvol = history_sorted[0].get("value")
        
        if previous_dvol is None:
            self.state_store.set("dvol", current_dvol, current_time)
            return
        
        # 计算变化
        if previous_dvol == 0:
            pct_change = 0.0
        else:
            pct_change = (current_dvol - previous_dvol) / previous_dvol
        abs_change = current_dvol - previous_dvol
        
        # 格式化变化信息
        change_sign = "+" if pct_change >= 0 else ""
        abs_sign = "+" if abs_change >= 0 else ""
        
        # 检查 DVOL 数值异动
        dvol_value_thresholds = self.dvol_thresholds.get("dvol_value", {})
        abs_value_threshold = dvol_value_thresholds.get("abs_threshold", 60.0)  # 绝对数值阈值
        pct_threshold = dvol_value_thresholds.get("pct_change_5m", 0.05)
        abs_change_threshold = dvol_value_thresholds.get("abs_change_5m", 5.0)
        
        # 输出变动情况（无论是否触发告警）
        logger.info(
            f"[DVOL 监控] DVOL 数值: "
            f"当前={current_dvol:.2f}, 5分钟前={previous_dvol:.2f}, "
            f"变化={change_sign}{pct_change*100:.2f}% ({abs_sign}{abs_change:.2f}), "
            f"绝对数值阈值={abs_value_threshold:.2f}, 变化阈值={pct_threshold*100:.2f}%/{abs_change_threshold:.2f}"
        )
        
        # 检查绝对数值预警
        should_alert_abs_value = current_dvol >= abs_value_threshold
        
        # 检查5分钟变化预警
        should_alert_change = (abs(pct_change) > pct_threshold) or (abs(abs_change) > abs_change_threshold)
        
        # 检查特定 DVOL 值预警
        specific_values = dvol_value_thresholds.get("specific_values", [])
        specific_tolerance = dvol_value_thresholds.get("specific_value_tolerance", 0.5)
        matched_specific_value = None
        
        for target_value in specific_values:
            if abs(current_dvol - target_value) <= specific_tolerance:
                matched_specific_value = target_value
                break
        
        # 特定值预警（优先检查）
        if matched_specific_value is not None:
            alert_key = f"dvol_specific_{matched_specific_value}"
            
            if self._should_alert(alert_key, current_time):
                if self.enable_alert:
                    title = f"🚨 DVOL 特定值预警 - {matched_specific_value}"
                    message = (
                        f"DVOL 当前值: {current_dvol:.2f}\n"
                        f"预警目标值: {matched_specific_value}\n"
                        f"容差范围: {matched_specific_value - specific_tolerance:.2f} ~ {matched_specific_value + specific_tolerance:.2f}\n"
                        f"5分钟前: {previous_dvol:.2f}\n"
                        f"⚠️ DVOL 已达到预警值 {matched_specific_value}！"
                    )
                    
                    detail = {
                        "当前 DVOL": f"{current_dvol:.2f}",
                        "预警目标值": f"{matched_specific_value}",
                        "容差范围": f"±{specific_tolerance:.2f}"
                    }
                    
                    success = send_feishu_alert(
                        title=title,
                        message=message,
                        webhook_url=self.feishu_webhook_url,
                        detail=detail
                    )
                    
                    if success:
                        self.state_store.set_last_alert_time(alert_key, current_time)
                        logger.warning(f"DVOL 特定值预警已发送: {current_dvol:.2f} 接近 {matched_specific_value}")
        
        # 绝对数值预警
        if should_alert_abs_value:
            alert_key = "dvol_abs_value"
            
            if self._should_alert(alert_key, current_time):
                if self.enable_alert:
                    title = f"🚨 DVOL 绝对数值预警"
                    message = (
                        f"DVOL 当前值: {current_dvol:.2f}\n"
                        f"预警阈值: {abs_value_threshold:.2f}\n"
                        f"5分钟前: {previous_dvol:.2f}\n"
                        f"⚠️ DVOL 已达到预警水平！"
                    )
                    
                    detail = {
                        "当前 DVOL": f"{current_dvol:.2f}",
                        "预警阈值": f"{abs_value_threshold:.2f}"
                    }
                    
                    success = send_feishu_alert(
                        title=title,
                        message=message,
                        webhook_url=self.feishu_webhook_url,
                        detail=detail
                    )
                    
                    if success:
                        self.state_store.set_last_alert_time(alert_key, current_time)
                        logger.warning(f"DVOL 绝对数值预警已发送: {current_dvol:.2f} >= {abs_value_threshold:.2f}")
        
        # 5分钟变化预警
        if should_alert_change:
            alert_key = "dvol_change"
            
            if self._should_alert(alert_key, current_time):
                if self.enable_alert:
                    title = f"⚠️ DVOL 异动告警"
                    message = (
                        f"DVOL 当前值: {current_dvol:.2f}\n"
                        f"5分钟前: {previous_dvol:.2f}\n"
                        f"变化: {change_sign}{pct_change*100:.2f}% ({abs_sign}{abs_change:.2f})\n"
                        f"触发条件: 5分钟变化超过 {pct_threshold*100:.2f}% 或绝对值变化超过 {abs_change_threshold:.2f}"
                    )
                    
                    detail = {
                        "触发条件": f"5 分钟变化 {pct_change*100:.2f}% (阈值: {pct_threshold*100:.2f}%) 或 绝对值变化 {abs_change:.2f} (阈值: {abs_change_threshold:.2f})"
                    }
                    
                    success = send_feishu_alert(
                        title=title,
                        message=message,
                        webhook_url=self.feishu_webhook_url,
                        detail=detail
                    )
                    
                    if success:
                        self.state_store.set_last_alert_time(alert_key, current_time)
                        logger.warning(f"DVOL 异动告警已发送: 变化 {pct_change*100:.2f}%")
        
        # 保存当前 DVOL 值
        self.state_store.set("dvol", current_dvol, current_time)
    
    def _should_alert(self, alert_key: str, current_time: float) -> bool:
        """
        判断是否应该发送告警（冷却时间检查）
        
        Args:
            alert_key: 告警键
            current_time: 当前时间戳
            
        Returns:
            是否应该告警
        """
        last_alert_time = self.state_store.get_last_alert_time(alert_key)
        
        if last_alert_time is None:
            return True
        
        elapsed = current_time - last_alert_time
        return elapsed >= self.cooldown_seconds

