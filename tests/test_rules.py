import os
import tempfile
import unittest

from hot_money_chasing.models import MoneyFlow, Quote, SectorFlow, StockSnapshot
from hot_money_chasing.rules import RuleEngine
from hot_money_chasing.settings import RuleSettings
from hot_money_chasing.storage import SQLiteStore


class RuleEngineTest(unittest.TestCase):
    def test_detects_volume_fund_and_sector_signals(self):
        settings = RuleSettings(
            price_breakout_pct=3.0,
            volume_ratio=1.5,
            min_turnover_amount=10000000,
            fund_spike_amount=30000000,
            fund_spike_pct=5.0,
            hot_sector_min_inflow=10000000,
        )
        engine = RuleEngine(settings)
        snapshot = StockSnapshot(
            quote=Quote(
                symbol="000001",
                name="平安银行",
                price=12.3,
                pct_change=4.2,
                volume_ratio=2.1,
                amount=50000000,
                sector="银行",
            ),
            money_flow=MoneyFlow(
                symbol="000001",
                name="平安银行",
                main_net_inflow=65000000,
                main_net_inflow_pct=9.1,
            ),
        )
        signals = engine.evaluate([snapshot], [SectorFlow("银行", main_net_inflow=500000000, rank=1)])
        signal_types = {signal.signal_type for signal in signals}
        self.assertIn("volume_price_breakout", signal_types)
        self.assertIn("fund_spike", signal_types)
        self.assertIn("sector_rotation", signal_types)

    def test_detects_continuous_inflow_with_store_history(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            store = SQLiteStore(path)
            flow1 = MoneyFlow(symbol="000001", name="平安银行", main_net_inflow=30000000)
            flow2 = MoneyFlow(symbol="000001", name="平安银行", main_net_inflow=35000000)
            store.save_money_flows([flow1, flow2])
            engine = RuleEngine(
                RuleSettings(
                    continuous_inflow_window=3,
                    continuous_inflow_min_total=90000000,
                    fund_spike_amount=999999999,
                    price_breakout_pct=99,
                    hot_sector_min_inflow=999999999,
                )
            )
            snapshot = StockSnapshot(
                quote=Quote(symbol="000001", name="平安银行", price=12, pct_change=1.0),
                money_flow=MoneyFlow(symbol="000001", name="平安银行", main_net_inflow=40000000),
            )
            signals = engine.evaluate([snapshot], [], store=store)
            self.assertEqual(["continuous_inflow"], [signal.signal_type for signal in signals])
            store.close()
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
