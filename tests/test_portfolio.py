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
