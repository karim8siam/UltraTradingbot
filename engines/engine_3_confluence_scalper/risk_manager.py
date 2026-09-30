from config import MAX_RISK_PER_TRADE, LEVERAGE, MAX_CONCURRENT_TRADES

class RiskManager:
    def __init__(self, max_risk_pct=MAX_RISK_PER_TRADE, leverage=LEVERAGE, max_trades=MAX_CONCURRENT_TRADES):
        self.max_risk_pct = max_risk_pct
        self.leverage = leverage
        self.max_trades = max_trades

    def calculate_position_size(self, equity, entry_price, sl_price):
        """
        Calculates position size strictly respecting:
        1. Max risk per trade <= 1.0% of total equity
        2. Max leverage <= 5x isolated
        """
        if equity <= 0 or entry_price <= 0:
            return 0.0, 0.0

        sl_distance_pct = abs(entry_price - sl_price) / entry_price
        if sl_distance_pct <= 0:
            return 0.0, 0.0

        # Max loss willing to take at Stop-Loss
        target_risk_dollars = equity * self.max_risk_pct

        # Position notional value required so that: Position Size * SL% = 1% Equity
        notional_size = target_risk_dollars / sl_distance_pct

        # Hard cap at maximum allowed leverage (e.g., 5x equity)
        max_notional = equity * self.leverage
        actual_notional = min(notional_size, max_notional)

        # Margin required from account
        margin_required = actual_notional / self.leverage
        quantity = actual_notional / entry_price

        return round(actual_notional, 2), round(quantity, 4)

    def can_open_trade(self, current_open_trades_count, equity, margin_required):
        """
        Checks concurrency and margin availability.
        """
        if current_open_trades_count >= self.max_trades:
            return False, f"Max concurrent trades reached ({self.max_trades})"

        if margin_required > equity * 0.9:
            return False, "Insufficient available margin"

        return True, "OK"
