"""程序主入口"""
import time
import signal
import sys
from loguru import logger

from config import load_config
from monitor import Monitor


class MonitorDaemon:
    """监控守护进程"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """初始化监控守护进程"""
        self.running = True
        self.config = load_config(config_path)
        self.monitor = Monitor(self.config)
        self.poll_interval = self.config.get("general", {}).get("poll_interval_seconds", 60)
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def run(self):
        """运行监控循环"""
        logger.info("=" * 60)
        logger.info("Deribit BTC 期权和 DVOL 监控系统启动")
        logger.info("=" * 60)
        logger.info(f"轮询间隔: {self.poll_interval} 秒")
        logger.info(f"监控标的: {self.config.get('deribit', {}).get('underlying', 'BTC')}")
        logger.info(f"告警启用: {self.config.get('alert', {}).get('enable_alert', True)}")
        logger.info(f"告警冷却时间: {self.config.get('alert', {}).get('cooldown_seconds', 300)} 秒")
        logger.info("-" * 60)
        
        try:
            while self.running:
                try:
                    # 执行一次监控循环
                    self.monitor.run()
                except KeyboardInterrupt:
                    logger.info("收到键盘中断，退出监控")
                    break
                except Exception as e:
                    logger.error(f"监控循环异常: {e}", exc_info=True)
                    # 即使出错也继续运行
                
                # 等待下一次轮询
                if self.running:
                    logger.debug(f"等待 {self.poll_interval} 秒后继续...")
                    time.sleep(self.poll_interval)
        
        except Exception as e:
            logger.error(f"监控守护进程异常: {e}", exc_info=True)
        finally:
            logger.info("监控系统已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deribit BTC 期权和 DVOL 监控系统")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）"
    )
    
    args = parser.parse_args()
    
    try:
        daemon = MonitorDaemon(config_path=args.config)
        daemon.run()
    except FileNotFoundError as e:
        logger.error(f"配置文件不存在: {e}")
        logger.error("请确保 config.yaml 文件存在，或使用 --config 参数指定配置文件路径")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

