"""Trading operations tests for MT5 API.

Tests order placement, validation, and calculation functions.
Uses actual order execution on demo account.

Markers:
    @pytest.mark.trading - Tests that place real orders
    @pytest.mark.slow - Tests that may take longer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestOrderCheck:
    """Order validation tests (order_check).

    Tests order validation without actually placing orders.
    """

    @pytest.mark.trading
    def test_order_check_valid_buy(
        self,
        mt5: MetaTrader5,
        buy_order_request: dict[str, Any],
    ) -> None:
        """Test order_check with valid buy request.

        Note: order_check may return None on some demo accounts.
        """
        result = mt5.order_check(buy_order_request)
        if result is None:
            pytest.skip("order_check returned None (not supported on this account)")
        assert result.retcode in {mt5.TRADE_RETCODE_DONE, 0}
        assert result.balance > 0
        assert result.equity > 0

    @pytest.mark.trading
    def test_order_check_valid_sell(
        self,
        mt5: MetaTrader5,
        sell_order_request: dict[str, Any],
    ) -> None:
        """Test order_check with valid sell request.

        Note: order_check may return None on some demo accounts.
        """
        result = mt5.order_check(sell_order_request)
        if result is None:
            pytest.skip("order_check returned None (not supported on this account)")
        assert result.balance > 0
        assert result.equity > 0

    @pytest.mark.trading
    def test_order_check_invalid_symbol(self, mt5: MetaTrader5) -> None:
        """Test order_check with invalid symbol."""
        tick = mt5.symbol_info_tick("EURUSD")
        invalid_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "INVALID_SYMBOL",
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask if tick else 1.0,
            "deviation": 20,
            "magic": 999999,
            "comment": "test_invalid",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_check(invalid_request)
        # Should return error or None
        if result is not None:
            assert result.retcode != mt5.TRADE_RETCODE_DONE

    @pytest.mark.trading
    def test_order_check_zero_volume(self, mt5: MetaTrader5) -> None:
        """Test order_check with zero volume."""
        tick = mt5.symbol_info_tick("EURUSD")
        invalid_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.0,  # Invalid volume
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask if tick else 1.0,
            "deviation": 20,
            "magic": 999999,
            "comment": "test_zero_volume",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_check(invalid_request)
        # Should fail validation
        if result is not None:
            assert result.retcode != mt5.TRADE_RETCODE_DONE


class TestOrderSend:
    """Order execution tests (order_send).

    Actually places orders on demo account.
    Uses cleanup_test_positions fixture to close test orders.
    """

    @pytest.mark.trading
    @pytest.mark.slow
    def test_order_send_buy_market(
        self,
        mt5: MetaTrader5,
        buy_order_request: dict[str, Any],
        cleanup_test_positions: None,
    ) -> None:
        """Test placing a market buy order.

        Note: order_send may return None on some demo accounts.
        """
        # Ensure symbol is selected
        mt5.symbol_select("EURUSD", True)

        result = mt5.order_send(buy_order_request)
        if result is None:
            pytest.skip("order_send returned None (not supported on this account)")

        # Check for success or common acceptable return codes
        acceptable_codes = [
            mt5.TRADE_RETCODE_DONE,  # Success
            mt5.TRADE_RETCODE_PLACED,  # Order placed
        ]

        if result.retcode not in acceptable_codes:
            # May fail on weekends/market closed
            market_closed_codes = [
                mt5.TRADE_RETCODE_MARKET_CLOSED,
                mt5.TRADE_RETCODE_NO_CHANGES,
            ]
            if result.retcode in market_closed_codes:
                pytest.skip(f"Market closed: {result.comment}")
            else:
                pytest.fail(
                    f"Order failed: retcode={result.retcode}, comment={result.comment}"
                )

        # Verify order details
        assert result.volume == buy_order_request["volume"]

    @pytest.mark.trading
    @pytest.mark.slow
    def test_order_send_sell_market(
        self,
        mt5: MetaTrader5,
        sell_order_request: dict[str, Any],
        cleanup_test_positions: None,
    ) -> None:
        """Test placing a market sell order.

        Note: order_send may return None on some demo accounts.
        """
        mt5.symbol_select("EURUSD", True)

        result = mt5.order_send(sell_order_request)
        if result is None:
            pytest.skip("order_send returned None (not supported on this account)")

        acceptable_codes = [
            mt5.TRADE_RETCODE_DONE,
            mt5.TRADE_RETCODE_PLACED,
        ]

        if result.retcode not in acceptable_codes:
            market_closed_codes = [
                mt5.TRADE_RETCODE_MARKET_CLOSED,
                mt5.TRADE_RETCODE_NO_CHANGES,
            ]
            if result.retcode in market_closed_codes:
                pytest.skip(f"Market closed: {result.comment}")
            else:
                pytest.fail(
                    f"Order failed: retcode={result.retcode}, comment={result.comment}"
                )

    @pytest.mark.trading
    @pytest.mark.slow
    def test_order_send_buy_limit(
        self,
        mt5: MetaTrader5,
        cleanup_test_positions: None,
    ) -> None:
        """Test placing a buy limit order.

        Note: order_send may return None on some demo accounts.
        """
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        # Place limit order below current price
        limit_price = round(tick.bid * 0.99, 5)  # 1% below

        limit_request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": "EURUSD",
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY_LIMIT,
            "price": limit_price,
            "deviation": 20,
            "magic": 999999,
            "comment": "test_buy_limit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(limit_request)
        if result is None:
            pytest.skip("order_send returned None (not supported on this account)")

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            # Cancel the pending order
            orders = mt5.orders_get(symbol="EURUSD")
            if orders:
                for order in orders:
                    if order.magic == 999999:
                        cancel_request = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket,
                        }
                        mt5.order_send(cancel_request)

    @pytest.mark.trading
    @pytest.mark.slow
    def test_order_send_close_position(
        self,
        mt5: MetaTrader5,
        buy_order_request: dict[str, Any],
    ) -> None:
        """Test opening and closing a position."""
        mt5.symbol_select("EURUSD", True)

        # Open position
        open_result = mt5.order_send(buy_order_request)

        if open_result is None or open_result.retcode != mt5.TRADE_RETCODE_DONE:
            pytest.skip("Could not open position for close test")

        # Get the position
        positions = mt5.positions_get(symbol="EURUSD")
        if not positions:
            pytest.skip("Position not found after opening")

        position = None
        for pos in positions:
            if pos.magic == 999999:
                position = pos
                break

        if position is None:
            pytest.skip("Test position not found")

        # Close the position
        tick = mt5.symbol_info_tick("EURUSD")
        close_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL,  # Opposite of buy
            "position": position.ticket,
            "price": tick.bid,
            "deviation": 20,
            "magic": 999999,
            "comment": "close_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        close_result = mt5.order_send(close_request)
        assert close_result is not None
        assert close_result.retcode == mt5.TRADE_RETCODE_DONE


class TestOrderCalc:
    """Order calculation tests (margin and profit)."""

    @pytest.mark.trading
    def test_order_calc_margin_buy(self, mt5: MetaTrader5) -> None:
        """Test margin calculation for buy order."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        margin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY,
            "EURUSD",
            0.1,  # 0.1 lots
            tick.ask,
        )

        assert margin is not None
        assert margin > 0

    @pytest.mark.trading
    def test_order_calc_margin_sell(self, mt5: MetaTrader5) -> None:
        """Test margin calculation for sell order."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        margin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_SELL,
            "EURUSD",
            0.1,
            tick.bid,
        )

        assert margin is not None
        assert margin > 0

    @pytest.mark.trading
    def test_order_calc_profit_buy_win(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for winning buy position."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        # Simulate buy at current price, close higher
        entry_price = tick.ask
        close_price = entry_price + 0.0010  # +10 pips

        profit = mt5.order_calc_profit(
            mt5.ORDER_TYPE_BUY,
            "EURUSD",
            0.1,
            entry_price,
            close_price,
        )

        if profit is None:
            pytest.skip("order_calc_profit returned None (not supported)")
        assert profit > 0  # Should be profitable

    @pytest.mark.trading
    def test_order_calc_profit_buy_loss(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for losing buy position."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        # Simulate buy at current price, close lower
        entry_price = tick.ask
        close_price = entry_price - 0.0010  # -10 pips

        profit = mt5.order_calc_profit(
            mt5.ORDER_TYPE_BUY,
            "EURUSD",
            0.1,
            entry_price,
            close_price,
        )

        assert profit is not None
        assert profit < 0  # Should be a loss

    @pytest.mark.trading
    def test_order_calc_profit_sell_win(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for winning sell position."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get EURUSD tick")

        # Simulate sell at current price, close lower
        entry_price = tick.bid
        close_price = entry_price - 0.0010  # -10 pips

        profit = mt5.order_calc_profit(
            mt5.ORDER_TYPE_SELL,
            "EURUSD",
            0.1,
            entry_price,
            close_price,
        )

        assert profit is not None
        assert profit > 0  # Should be profitable
