import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.simulate_market import generate_smc_market_data
from strategy.state_machine import SymbolStateMachine
from strategy.setup_evaluator import SetupEvaluator
from config import Config

data = generate_smc_market_data(num_days=3)
c4h = data["4h"]
c1h = data["1h"]
c15m = data["15m"]
c5m = data["5m"]

config = Config()
evaluator = SetupEvaluator(
    min_rr=config.MIN_RR,
    min_score=config.MIN_SETUP_SCORE,
    sl_atr_multiplier=config.SL_ATR_BUFFER_MULTIPLIER,
    max_atr_ratio=config.MAX_ATR_RATIO,
    allowed_sessions=config.ALLOWED_SESSIONS
)
sm = SymbolStateMachine("BTCUSDT", evaluator, swing_length=2)

for i in range(100, len(c5m)):
    curr_5m = c5m[:i+1]
    curr_ts = curr_5m[-1].timestamp
    s4h = [c for c in c4h if c.timestamp <= curr_ts]
    s1h = [c for c in c1h if c.timestamp <= curr_ts]
    s15m = [c for c in c15m if c.timestamp <= curr_ts]
    
    setup, status = sm.process_candles(s4h, s1h, s15m, curr_5m)
    if sm.state.value != "WAITING":
        print(f"Bar {i} (ts {curr_ts}): State={sm.state.value}, Status={status}, 4H={sm.bias_4h.value}, 1H={sm.bias_1h.value}")
    if setup:
        print(f"*** VALID SETUP FOUND at Bar {i}! Score={setup.setup_score}, RR={setup.rr:.2f}, Entry={setup.entry_price}, SL={setup.stop_loss}, TP={setup.take_profit} ***")
