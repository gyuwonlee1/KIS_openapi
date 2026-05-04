from __future__ import annotations

import unittest

from kis_alert_bot.portfolio import parse_portfolio


class PortfolioTests(unittest.TestCase):
    def test_loads_valid_portfolio(self) -> None:
        stocks = parse_portfolio(
            {
                "stocks": [
                    {
                        "name": "Apple",
                        "ticker": "AAPL",
                        "market": "US",
                        "exchange": "NASD",
                        "conditions": [
                            {
                                "id": "price",
                                "type": "price",
                                "operator": ">=",
                                "target": 200,
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0].exchange, "NASD")
        self.assertFalse(stocks[0].conditions[0].delete_after_alert)

    def test_loads_delete_after_alert(self) -> None:
        stocks = parse_portfolio(
            {
                "stocks": [
                    {
                        "name": "Samsung",
                        "ticker": "005930",
                        "market": "KR",
                        "conditions": [
                            {
                                "id": "price",
                                "type": "price",
                                "operator": ">=",
                                "target": 80000,
                                "delete_after_alert": True,
                            }
                        ],
                    }
                ]
            }
        )

        self.assertTrue(stocks[0].conditions[0].delete_after_alert)

    def test_rejects_invalid_operator(self) -> None:
        with self.assertRaises(ValueError):
            parse_portfolio(
                {
                    "stocks": [
                        {
                            "name": "Samsung",
                            "ticker": "005930",
                            "market": "KR",
                            "conditions": [
                                {
                                    "id": "bad",
                                    "type": "price",
                                    "operator": ">",
                                    "target": 100,
                                }
                            ],
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
