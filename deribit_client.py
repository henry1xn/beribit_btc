"""Deribit API 客户端封装"""
import time
import requests
import json
from datetime import datetime as dt
from typing import List, Dict, Any, Optional
from loguru import logger
from dataclasses import dataclass


@dataclass
class OptionPosition:
    """期权持仓数据类"""
    instrument_name: str
    kind: str
    direction: str  # "buy" or "sell"
    size: float
    mark_iv: float
    gamma: float
    delta: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


@dataclass
class DvolData:
    """DVOL 数据类"""
    value: float
    timestamp: float
    iv_percentile: Optional[float] = None  # IV 百分位（将在监控模块中计算）


class DeribitClient:
    """Deribit API 客户端"""
    
    def __init__(self, client_id: str, client_secret: str, base_url: str = "https://www.deribit.com"):
        """
        初始化 Deribit 客户端
        
        Args:
            client_id: Deribit Client ID
            client_secret: Deribit Client Secret
            base_url: Deribit API 基础 URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v2"
        self.token = None
        self.token_expires_at = 0
        self.request_id = 0
        self.authenticate()
    
    def _get_next_request_id(self) -> int:
        """获取下一个请求 ID"""
        self.request_id += 1
        return self.request_id
    
    def _make_request(
        self, 
        method_name: str, 
        params: Optional[Dict] = None, 
        retry_times: int = 3
    ) -> Optional[Dict]:
        """
        发送 JSON-RPC 2.0 请求（带重试机制）
        
        Deribit API v2 使用 JSON-RPC 2.0 格式：
        {
            "jsonrpc": "2.0",
            "method": "public/auth",
            "params": {...},
            "id": 1
        }
        
        Args:
            method_name: API 方法名（如 "public/auth", "private/get_positions"）
            params: 请求参数
            retry_times: 重试次数
            
        Returns:
            API 响应 result 字段，失败返回 None
        """
        url = self.api_url
        headers = {"Content-Type": "application/json"}
        
        # 如果是私有接口，添加认证 token
        if method_name.startswith("private/"):
            if not self.token or time.time() >= self.token_expires_at:
                if not self.authenticate():
                    return None
            headers["Authorization"] = f"Bearer {self.token}"
        
        # 构建 JSON-RPC 2.0 请求体
        request_body = {
            "jsonrpc": "2.0",
            "method": method_name,
            "id": self._get_next_request_id()
        }
        
        if params:
            request_body["params"] = params
        
        for attempt in range(retry_times):
            try:
                # 增加超时时间：30 秒连接超时，60 秒读取超时
                # 对于网络不稳定的情况，给更多时间
                response = requests.post(
                    url, 
                    json=request_body, 
                    headers=headers, 
                    timeout=(30, 60)  # (连接超时, 读取超时)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 检查 JSON-RPC 错误
                    if "error" in result and result["error"]:
                        error_code = result["error"].get("code", "unknown")
                        error_msg = result["error"].get("message", "未知错误")
                        error_data = result["error"].get("data", {})
                        
                        # 如果是认证错误，尝试重新认证
                        if error_code in (13009, 13000) and "unauthorized" in error_msg.lower():
                            logger.warning("Token 过期或无效，重新认证...")
                            if method_name.startswith("private/"):
                                if not self.authenticate():
                                    return None
                                headers["Authorization"] = f"Bearer {self.token}"
                                if attempt < retry_times - 1:
                                    continue
                        
                        logger.error(f"Deribit API 错误 [{error_code}]: {error_msg}")
                        if error_data:
                            logger.debug(f"错误详情: {error_data}")
                        return None
                    
                    # 返回 result 字段
                    return result.get("result")
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text}")
                    if attempt < retry_times - 1:
                        wait_time = 2 ** attempt  # 指数退避
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    
            except requests.exceptions.Timeout as e:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                if attempt < retry_times - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"请求超时，已重试 {retry_times} 次，放弃请求")
            except requests.exceptions.SSLError as e:
                logger.warning(f"SSL 连接错误 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                if attempt < retry_times - 1:
                    wait_time = 3 + (2 ** attempt)  # SSL 错误时等待更长时间
                    logger.info(f"SSL 错误，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"SSL 连接错误，已重试 {retry_times} 次，放弃请求")
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求异常 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                if attempt < retry_times - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"请求失败，已重试 {retry_times} 次，放弃请求")
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析错误: {e}")
                return None
            except Exception as e:
                logger.error(f"未知错误 (尝试 {attempt + 1}/{retry_times}): {type(e).__name__}: {str(e)}")
                if attempt < retry_times - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
        
        return None
    
    def authenticate(self) -> bool:
        """
        认证并获取访问 token
        
        Returns:
            认证是否成功
        """
        method_name = "public/auth"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        result = self._make_request(method_name, params=params, retry_times=1)
        
        if result:
            self.token = result.get("access_token")
            expires_in = result.get("expires_in", 3600)  # 默认 1 小时
            self.token_expires_at = time.time() + expires_in - 60  # 提前 1 分钟过期
            logger.info("Deribit 认证成功")
            return True
        else:
            logger.error("Deribit 认证失败，请检查 Client ID 和 Client Secret")
            return False
    
    def get_account_option_positions(self, currency: str = "BTC", kind: str = "option") -> List[OptionPosition]:
        """
        获取账户期权持仓及其 Greeks
        
        Args:
            currency: 货币，如 "BTC"
            kind: 合约类型，如 "option"
            
        Returns:
            期权持仓列表
        """
        method_name = "private/get_positions"
        params = {
            "currency": currency,
            "kind": kind
        }
        
        result = self._make_request(method_name, params=params)
        
        if result is None:
            return []
        
        # result 可能是列表或单个持仓对象
        if not isinstance(result, list):
            result = [result]
        
        if len(result) == 0:
            return []
        
        positions = []
        for pos in result:
            # 只保留有效持仓（size != 0）
            size = float(pos.get("size", 0))
            if abs(size) < 1e-8:
                continue
            
            instrument_name = pos.get("instrument_name", "")
            
            # 直接从 private/get_positions API 获取持仓的 Gamma（总持仓 Gamma）
            # 根据测试结果，position.gamma 是总持仓 Gamma（已乘以 size），直接使用
            mark_iv = float(pos.get("mark_iv", 0) or 0)
            
            # Gamma, Delta, Theta, Vega 直接从 position 对象中获取（总持仓值）
            gamma = float(pos.get("gamma", 0) or 0)
            delta = float(pos.get("delta", 0) or 0)
            theta = float(pos.get("theta", 0) or 0)
            vega = float(pos.get("vega", 0) or 0)
            
            # 如果有 greeks 字典，也尝试从中获取（作为备选）
            greeks = pos.get("greeks", {})
            if greeks and isinstance(greeks, dict):
                # 如果 position 中的值为 0，尝试从 greeks 字典获取
                if abs(gamma) < 1e-8:
                    gamma = float(greeks.get("gamma", 0) or 0)
                if abs(delta) < 1e-8:
                    delta = float(greeks.get("delta", 0) or 0)
                if abs(theta) < 1e-8:
                    theta = float(greeks.get("theta", 0) or 0)
                if abs(vega) < 1e-8:
                    vega = float(greeks.get("vega", 0) or 0)
            
            # 优先从 public/get_order_book 获取单个合约的 Greeks
            # get_order_book 返回的是单个合约的 Gamma，需要乘以持仓量得到总持仓 Gamma
            order_book = self._make_request(
                "public/get_order_book",
                params={"instrument_name": instrument_name, "depth": 1}
            )
            
            if order_book and "greeks" in order_book:
                greeks_from_orderbook = order_book.get("greeks", {})
                if isinstance(greeks_from_orderbook, dict) and "gamma" in greeks_from_orderbook:
                    # 获取单个合约的 Gamma 和 Vega
                    gamma_per_unit = float(greeks_from_orderbook.get("gamma", 0) or 0)
                    vega_per_unit = float(greeks_from_orderbook.get("vega", 0) or 0)
                    
                    # 乘以持仓量得到总持仓 Gamma 和 Vega
                    if abs(size) > 1e-8:
                        gamma_total = abs(gamma_per_unit) * abs(size)
                        vega_total = abs(vega_per_unit) * abs(size)
                    else:
                        gamma_total = abs(gamma_per_unit)
                        vega_total = abs(vega_per_unit)
                    
                    logger.info(
                        f"{instrument_name}: size={size:.4f}, "
                        f"单个合约Gamma={abs(gamma_per_unit):.8f}, "
                        f"总持仓Gamma={gamma_total:.8f} (乘以size后)"
                    )
                    
                    # 使用总持仓 Gamma（乘以 size 后）
                    gamma = gamma_total
                    vega = vega_total
                else:
                    # 回退到从 position 获取（已经是总持仓值）
                    gamma = abs(gamma)
                    vega = abs(vega)
                    
                    logger.info(
                        f"{instrument_name}: size={size:.4f}, "
                        f"API Gamma(总持仓)={gamma:.10f} (从position获取)"
                    )
            else:
                # 如果 order_book 失败，回退到从 position 获取（已经是总持仓值）
                gamma = abs(gamma)
                vega = abs(vega)
                
                logger.info(
                    f"{instrument_name}: size={size:.4f}, "
                    f"API Gamma(总持仓)={gamma:.10f} (从position获取, get_order_book失败)"
                )
            
            position = OptionPosition(
                instrument_name=instrument_name,
                kind=pos.get("kind", kind),
                direction="buy" if size > 0 else "sell",
                size=abs(size),
                mark_iv=mark_iv,
                gamma=gamma,
                delta=delta,
                theta=theta,
                vega=vega
            )
            positions.append(position)
        
        return positions
    
    def get_open_orders(self, currency: str = "BTC", kind: str = None) -> List[Dict]:
        """
        获取账户当前挂单
        
        Args:
            currency: 货币，如 "BTC"
            kind: 合约类型，如 "option", "future" 等，None 表示获取所有类型
            
        Returns:
            挂单列表
        """
        method_name = "private/get_open_orders_by_currency"
        params = {
            "currency": currency
        }
        
        # 先尝试不传 kind 参数，获取所有类型的挂单
        # 然后我们手动过滤期权类型的挂单
        result = self._make_request(method_name, params=params)
        
        if result is None:
            logger.warning("获取挂单失败：API 返回 None")
            return []
        
        # result 可能是列表或单个订单对象
        if not isinstance(result, list):
            result = [result]
        
        logger.debug(f"API 返回了 {len(result)} 个挂单（所有类型）")
        
        # 如果没有结果，尝试不传 kind 参数再次获取
        if len(result) == 0:
            logger.debug("未获取到挂单，尝试获取所有类型的挂单...")
            # 这里已经是不传 kind 了，如果还是空，说明确实没有挂单
            return []
        
        orders = []
        for order in result:
            order_kind = order.get("kind", "")
            
            # 如果指定了 kind，过滤出匹配的类型
            if kind and order_kind != kind:
                logger.debug(f"跳过非 {kind} 类型挂单: {order.get('instrument_name', 'unknown')} (类型: {order_kind})")
                continue
            
            order_info = {
                "order_id": order.get("order_id", ""),
                "instrument_name": order.get("instrument_name", ""),
                "direction": order.get("direction", ""),  # "buy" or "sell"
                "price": float(order.get("price", 0)),
                "amount": float(order.get("amount", 0)),
                "filled": float(order.get("filled_amount", 0)),
                "remaining": float(order.get("amount", 0)) - float(order.get("filled_amount", 0)),
                "order_type": order.get("order_type", ""),  # "limit", "market", etc.
                "order_state": order.get("order_state", ""),  # "open", "filled", etc.
                "time_in_force": order.get("time_in_force", ""),  # "good_til_cancelled", etc.
                "kind": order_kind,
                "creation_timestamp": order.get("creation_timestamp", 0),
                "last_update_timestamp": order.get("last_update_timestamp", 0)
            }
            orders.append(order_info)
            logger.debug(f"添加挂单: {order_info['instrument_name']}, 类型={order_kind}, 方向={order_info['direction']}")
        
        logger.info(f"获取到 {len(orders)} 个{'期权' if kind == 'option' else ''}挂单（从 {len(result)} 个总挂单中过滤）")
        
        return orders
    
    def get_btc_dvol(self) -> Optional[DvolData]:
        """
        获取 BTC DVOL (Volatility Index) 数据
        
        根据 Deribit API 文档，DVOL 数据通过 get_volatility_index_data 获取
        对应网页: https://www.deribit.com/statistics/BTC/volatility-index
        
        注意：该 API 需要 start_timestamp、end_timestamp 和 resolution 参数
        
        Returns:
            DVOL 数据，失败返回 None
        """
        method_name = "public/get_volatility_index_data"
        
        # 获取最近的数据（以毫秒为单位）
        # 使用较小的分辨率以获取更实时的数据
        end_timestamp = int(time.time() * 1000)
        
        # 使用 "1H" (1小时) 分辨率获取最近 2 天的数据
        # 这样既能获取到最新的值，又有足够的历史数据
        start_timestamp = end_timestamp - (2 * 24 * 60 * 60 * 1000)  # 2 天前
        
        # resolution: 时间分辨率
        # 可选值: "1D" (1天), "1H" (1小时), "1M" (1分钟) 等
        # 使用 "1H" 可以获取更实时的 DVOL 值
        params = {
            "currency": "BTC",
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "resolution": "1H"  # 使用 1 小时分辨率，获取更实时的数据
        }
        
        result = self._make_request(method_name, params=params)
        
        if not result:
            logger.warning("获取 DVOL 数据失败")
            return None
        
        # Deribit API 返回格式：
        # {
        #   "data": [
        #     [timestamp, open, high, low, close],  // OHLC 格式
        #     ...
        #   ],
        #   "continuation": None
        # }
        
        if isinstance(result, dict):
            data_array = result.get("data", [])
            if not data_array or len(data_array) == 0:
                logger.warning("DVOL 数据为空")
                return None
            
            # 获取最新的数据点（通常是最后一个）
            # 数据格式: [timestamp(ms), open, high, low, close]
            latest = data_array[-1]
            
            if not isinstance(latest, list) or len(latest) < 5:
                logger.error(f"DVOL 数据格式异常，期望 OHLC 数组: {latest}")
                return None
            
            # 提取数据：timestamp, open, high, low, close
            timestamp_ms = int(latest[0])  # 时间戳（毫秒）
            dvol_value = float(latest[4])  # close 值作为当前 DVOL
            
            # 转换为秒级时间戳
            timestamp = timestamp_ms / 1000.0
            
            # 转换为可读时间
            readable_time = dt.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            logger.info(f"获取 DVOL: {dvol_value:.2f} (时间: {readable_time})")
            logger.debug(f"DVOL 详细数据: 时间戳={timestamp_ms}, OHLC=[{latest[1]:.2f}, {latest[2]:.2f}, {latest[3]:.2f}, {latest[4]:.2f}]")
            
            return DvolData(
                value=dvol_value,
                timestamp=timestamp
            )
        elif isinstance(result, list):
            # 如果直接返回数组（旧格式兼容）
            if len(result) == 0:
                logger.warning("DVOL 数据为空")
                return None
            
            latest = result[-1]
            if isinstance(latest, dict):
                dvol_value = latest.get("volatility") or latest.get("value")
                timestamp_ms = latest.get("timestamp", int(time.time() * 1000))
                if dvol_value is None:
                    logger.error(f"无法从 DVOL 数据中提取数值: {latest}")
                    return None
                timestamp = timestamp_ms / 1000.0 if timestamp_ms > 1000000000000 else time.time()
                return DvolData(value=float(dvol_value), timestamp=timestamp)
            else:
                logger.error(f"DVOL 数据格式异常: {result}")
                return None
        else:
            logger.error(f"DVOL 数据格式异常: {result}")
            return None
    
    def get_dvol_history(self, currency: str = "BTC", start_timestamp: int = None, end_timestamp: int = None, resolution: str = "1D") -> List[Dict]:
        """
        获取 DVOL 历史数据（用于计算百分位）
        
        Args:
            currency: 货币，如 "BTC"
            start_timestamp: 开始时间戳（毫秒），如果为 None 则使用默认值
            end_timestamp: 结束时间戳（毫秒），如果为 None 则使用当前时间
            resolution: 时间分辨率，如 "1D" (1天), "1H" (1小时) 等
            
        Returns:
            DVOL 历史数据列表
        """
        method_name = "public/get_volatility_index_data"
        
        if end_timestamp is None:
            end_timestamp = int(time.time() * 1000)
        if start_timestamp is None:
            # 默认获取最近 30 天的数据
            start_timestamp = end_timestamp - (30 * 24 * 60 * 60 * 1000)
        
        params = {
            "currency": currency,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "resolution": resolution  # 必需参数
        }
        
        result = self._make_request(method_name, params=params)
        
        if not result:
            return []
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []

