import unittest
from state_machine import SymbolStateMachine, BotState


class TestStateMachine(unittest.TestCase):
    def test_state_transitions(self):
        sm = SymbolStateMachine("BTCUSDT")
        self.assertEqual(sm.current_state, BotState.WAITING)

        sm.transition_to(BotState.DAILY_TREND_CONFIRMED, "1D Bullish")
        self.assertEqual(sm.current_state, BotState.DAILY_TREND_CONFIRMED)

        sm.transition_to(BotState.SON_TIMEFRAME_MONITORING, "Monitoring 15M")
        self.assertEqual(sm.current_state, BotState.SON_TIMEFRAME_MONITORING)

        for _ in range(19):
            expired = sm.increment_setup_age(max_age=20)
            self.assertFalse(expired)

        # 20th candle
        expired = sm.increment_setup_age(max_age=20)
        self.assertTrue(expired)
        self.assertEqual(sm.current_state, BotState.EXPIRED)


if __name__ == "__main__":
    unittest.main()
