import unittest

import pandas as pd

from app.charts.whale_monitor import build_whale_inflow_monitor


class WhaleMonitorTests(unittest.TestCase):
    def test_hover_shows_inflow_and_transaction_count_without_address(self):
        data = pd.DataFrame({
            'output_address': ['private-address'],
            'total_output_value': [12_500.0],
            'transaction_count': [4],
        })

        trace = build_whale_inflow_monitor(data).data[0]

        self.assertIn('BTC Inflow:', trace.hovertemplate)
        self.assertIn('Transactions:', trace.hovertemplate)
        self.assertNotIn('Address:', trace.hovertemplate)
        self.assertEqual(list(trace.customdata[0]), [4])


if __name__ == '__main__':
    unittest.main()