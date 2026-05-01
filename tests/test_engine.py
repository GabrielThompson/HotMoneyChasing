import os
import tempfile
import unittest

from hot_money_chasing.engine import HotMoneyAgent
from hot_money_chasing.providers.mock_provider import MockProvider
from hot_money_chasing.settings import Settings
from hot_money_chasing.models import WatchItem
from hot_money_chasing.storage import SQLiteStore


class HotMoneyAgentTest(unittest.TestCase):
    def test_run_once_with_mock_provider(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            settings = Settings()
            settings.data.provider = "mock"
            settings.data.database_path = path
            settings.openclaw.enabled = False
            store = SQLiteStore(path)
            agent = HotMoneyAgent(settings, MockProvider(), store)
            result = agent.run_once(
                [
                    WatchItem("000001", "平安银行", sector="人工智能"),
                    WatchItem("000002", "万科A", sector="新能源汽车"),
                ]
            )
            self.assertEqual(2, len(result.snapshots))
            self.assertTrue(result.report.raw_text)
            self.assertGreater(len(result.signals), 0)
            store.close()
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
