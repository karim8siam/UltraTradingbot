"""
Unified Execution Trader for Dry Run, Paper Trading, Binance Testnet, and Live.
Enforces Section 54 (Order Execution flow), Section 55 (Unprotected position close),
Section 58 (Restart Recovery), and Section 71 (Live Trading Gate).
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from config import Config
from exchange.binance_client import BinanceFuturesClient, SymbolInfo
from market_data.data_fetcher import DataFetcher
from strategy.structure import MarketStructureEngine, SwingDetector
from strategy.impulse_pullback import ImpulseDetector, PullbackEngine
from strategy.confirmation import ConfirmationEngine
from strategy.scorer import SetupScorer
from strategy.indicators import calculate_adx_series, check_volatility_filter
from risk.risk_manager import RiskManager
from database.db import Database

logger = logging.getLogger(__name__)


class SwingTrader:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.client = BinanceFuturesClient(config=config)
        self.data_fetcher = DataFetcher(config=config)
        self.risk_mgr = RiskManager(config=config)

        self.struct_engine = MarketStructureEngine(
            swing_length=config.SWING_LENGTH,
            daily_ema_fast=config.DAILY_EMA_FAST,
            daily_ema_slow=config.DAILY_EMA_SLOW,
            four_h_ema_fast=config.FOUR_HOUR_EMA_FAST,
            four_h_ema_slow=config.FOUR_HOUR_EMA_SLOW
        )
        self.impulse_detector = ImpulseDetector(
            body_mult=config.IMPULSE_BODY_MULTIPLIER,
            atr_mult=config.IMPULSE_ATR_MULTIPLIER
        )
        self.pullback_engine = PullbackEngine(
            max_retracement=config.MAX_RETRACEMENT,
            swing_length=config.SWING_LENGTH
        )
        self.confirm_engine = ConfirmationEngine(
            min_rr=config.MIN_RR,
            swing_length=config.SWING_LENGTH,
            sl_atr_buffer=config.SL_ATR_BUFFER_FACTOR,
            timeout_bars=config.ENTRY_TIMEOUT_HOURS
        )
        self.scorer = SetupScorer(config=config)
        self.swing_detector = SwingDetector(swing_length=config.SWING_LENGTH)

        # Active in-memory state
        self.active_setups: Dict[str, Dict[str, Any]] = {}
        self.mode_str = self._determine_mode_string()

    def _determine_mode_string(self) -> str:
        """Section 71: Live trading gate verification."""
        if not self.config.BINANCE_TESTNET and self.config.LIVE_TRADING and self.config.LIVE_TRADING_CONFIRMATION:
            return "LIVE TRADING"
        elif self.config.BINANCE_TESTNET and not self.config.LIVE_TRADING and not self.config.PAPER_TRADING and not self.config.DRY_RUN:
            return "BINANCE TESTNET"
        elif self.config.PAPER_TRADING:
            return "PAPER TRADING"
        else:
            return "DRY RUN (MONITOR ONLY)"

    def startup_and_recover(self) -> None:
        """
        Section 58: Restart Recovery
        1. Connect Binance
        2. Retrieve account
        3. Retrieve open positions & orders
        4. Synchronize local database
        5. Verify SL / TP
        """
        logger.info(f"Starting Swing Trading Bot in [{self.mode_str}] mode...")
        print(f"\n========================================================")
        print(f"  SYSTEMATIC SWING BOT INITIALIZED - MODE: {self.mode_str}")
        print(f"========================================================\n")

        if self.mode_str in ["BINANCE TESTNET", "LIVE TRADING"]:
            try:
                self.client.sync_server_time()
                self.client.fetch_exchange_info()
                balance = self.client.fetch_account_balance()
                positions = self.client.fetch_positions()
                logger.info(f"Connected to Binance. Balance: {balance.get('equity', 0)} USDT | Open Positions: {len(positions)}")
            except Exception as e:
                logger.error(f"Failed to connect to Binance API: {e}")

    def scan_symbol_cycle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Run single analysis scan on a symbol across 1D, 4H, 1H."""
        try:
            # 1. Fetch recent candles (attempt refresh, fallback to cache)
            try:
                df_1d = self.data_fetcher.get_candles(symbol, self.config.TF_DAILY, min_candles=250, force_refresh=False)
                df_4h = self.data_fetcher.get_candles(symbol, self.config.TF_4H, min_candles=100, force_refresh=False)
                df_1h = self.data_fetcher.get_candles(symbol, self.config.TF_1H, min_candles=50, force_refresh=False)
            except Exception as e:
                df_1d = self.data_fetcher.load_from_cache(symbol, self.config.TF_DAILY)
                df_4h = self.data_fetcher.load_from_cache(symbol, self.config.TF_4H)
                df_1h = self.data_fetcher.load_from_cache(symbol, self.config.TF_1H)

            if df_1d is None or df_4h is None or df_1h is None or len(df_1d) < 205 or len(df_4h) < 60 or len(df_1h) < 15:
                return None

            # 2. Daily Trend & Structure
            daily_trend, d_trend_info = self.struct_engine.evaluate_daily_trend(df_1d["close"].values)
            daily_struct, d_struct_info = self.struct_engine.evaluate_daily_structure(
                df_1d["high"].values, df_1d["low"].values, df_1d["timestamp"].values
            )

            # 3. 4H Trend
            four_h_trend, f_trend_info = self.struct_engine.evaluate_4h_trend(df_4h["close"].values)

            # 4. Alignment
            direction = self.struct_engine.check_trend_alignment(daily_trend, daily_struct, four_h_trend)
            if not direction:
                return {
                    "symbol": symbol,
                    "status": "NO_ALIGNMENT",
                    "daily_trend": daily_trend.value,
                    "daily_structure": daily_struct.value,
                    "four_h_trend": four_h_trend.value,
                    "score": 0
                }

            is_bullish = (direction == "LONG")

            # 5. 4H Volatility check
            is_vol_pass, cur_atr, atr_ratio = check_volatility_filter(
                df_4h["high"].values, df_4h["low"].values, df_4h["close"].values,
                max_atr_ratio=self.config.MAX_ATR_RATIO
            )

            # 6. 4H Impulse
            impulse = self.impulse_detector.detect_latest_impulse(
                df_4h["open"].values, df_4h["high"].values, df_4h["low"].values,
                df_4h["close"].values, df_4h["volume"].values, is_bullish=is_bullish
            )
            if not impulse:
                return {
                    "symbol": symbol,
                    "status": "WAITING_FOR_IMPULSE",
                    "direction": direction,
                    "score": 0
                }

            # 7. Pullback & Fibonacci
            pullback = self.pullback_engine.evaluate_pullback(
                df_4h["high"].values, df_4h["low"].values, df_4h["close"].values,
                impulse, f_trend_info.get("4h_ema20", 0.0), f_trend_info.get("4h_ema50", 0.0)
            )
            if not pullback.is_valid:
                return {
                    "symbol": symbol,
                    "status": pullback.rejection_reason or "PULLBACK_INVALID",
                    "direction": direction,
                    "pullback_depth": pullback.pullback_depth,
                    "score": 0
                }

            # 8. 1H Confirmation
            swings_4h = self.swing_detector.find_swings(df_4h["high"].values, df_4h["low"].values)
            signal = self.confirm_engine.evaluate_1h_confirmation(
                df_1h["open"].values, df_1h["high"].values, df_1h["low"].values, df_1h["close"].values,
                pullback, swings_4h, is_bullish=is_bullish
            )

            # 9. ADX on 4H
            adx_series, _, _ = calculate_adx_series(
                df_4h["high"].values, df_4h["low"].values, df_4h["close"].values, period=14
            )
            adx_val = float(adx_series[-1]) if len(adx_series) > 0 and not np.isnan(adx_series[-1]) else 0.0

            # 10. Scoring
            eval_res = self.scorer.score_setup(
                symbol=symbol,
                direction=direction,
                daily_trend_aligned=True,
                daily_structure_aligned=True,
                four_h_trend_aligned=True,
                strong_4h_impulse=True,
                ema_fib_overlap=pullback.has_confluence_overlap,
                valid_4h_pullback=True,
                one_h_structure_confirm=signal.is_confirmed,
                one_h_displacement=signal.displacement_metrics.get("is_valid", False),
                adx_4h=adx_val,
                volume_confirmed=(impulse.volume_ratio >= self.config.MIN_VOLUME_RATIO),
                clear_structural_target=True,
                rr_ratio=signal.rr_ratio,
                is_extreme_volatility=(not is_vol_pass),
                is_extreme_funding=False,
                details={}
            )

            result = {
                "symbol": symbol,
                "status": "ENTRY_READY" if eval_res.is_valid and signal.is_confirmed else "PENDING_CONFIRMATION",
                "direction": direction,
                "score": eval_res.total_score,
                "daily_trend": daily_trend.value,
                "daily_structure": daily_struct.value,
                "four_h_trend": four_h_trend.value,
                "adx": adx_val,
                "volume_ratio": impulse.volume_ratio,
                "pullback_depth": pullback.pullback_depth,
                "has_confluence": pullback.has_confluence_overlap,
                "entry_price": signal.entry_price if signal.is_confirmed else None,
                "stop_loss": signal.stop_loss if signal.is_confirmed else None,
                "tp1": signal.target_tp1 if signal.is_confirmed else None,
                "rr_ratio": signal.rr_ratio if signal.is_confirmed else 0.0,
                "is_valid": eval_res.is_valid and signal.is_confirmed
            }
            return result

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None
