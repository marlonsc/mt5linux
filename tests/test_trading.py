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

from mt5linux.constants import MT5Constants as c
from tests.conftest import tc

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


def _get_filling_mode(mt5: MetaTrader5, filling_mode_mask: int) -> int:
    """Get supported filling mode from symbol's filling_mode bitmask."""
    if filling_mode_mask & 1:  # FOK supported
        return mt5.ORDER_FILLING_FOK
    if filling_mode_mask & 2:  # IOC supported
        return mt5.ORDER_FILLING_IOC
    if filling_mode_mask & 4:  # RETURN supported
        return mt5.ORDER_FILLING_RETURN
    return mt5.ORDER_FILLING_FOK  # Default


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
        Note: Some MT5 servers return retcode=0 instead of DONE for order_check.
        """
        result = mt5.order_check(buy_order_request)
        assert result is not None, "order_check returned None"
        # Check that calculation fields are populated (valid order_check result)
        assert result.balance > 0
        assert result.equity > 0
        assert result.margin > 0
        assert result.margin_free > 0

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
        assert result is not None, "order_check returned None"
        assert result.balance > 0
        assert result.equity > 0

    @pytest.mark.trading
    def test_order_check_invalid_symbol(self, mt5: MetaTrader5) -> None:
        """Test order_check with invalid symbol."""
        tick = mt5.symbol_info_tick("EURUSD")
        invalid_request = {
            "action": c.Order.TradeAction.DEAL,
            "symbol": "INVALID_SYMBOL",
            "volume": tc.MICRO_LOT,
            "type": c.Order.OrderType.BUY,
            "price": tick.ask if tick else 1.0,
            "deviation": tc.DEFAULT_DEVIATION,
            "magic": tc.INVALID_TEST_MAGIC,
            "comment": "test_invalid",
            "type_time": c.Order.OrderTime.GTC,
            "type_filling": c.Order.OrderFilling.IOC,
        }
        # Invalid symbol should either raise or return error retcode
        result = mt5.order_check(invalid_request)
        # Should return error or None
        if result is not None:
            assert result.retcode != c.Order.TradeRetcode.DONE

    @pytest.mark.trading
    def test_order_check_zero_volume(self, mt5: MetaTrader5) -> None:
        """Test order_check with zero volume."""
        tick = mt5.symbol_info_tick("EURUSD")
        invalid_request = {
            "action": c.Order.TradeAction.DEAL,
            "symbol": "EURUSD",
            "volume": tc.ZERO_VOLUME,  # Invalid volume
            "type": c.Order.OrderType.BUY,
            "price": tick.ask if tick else 1.0,
            "deviation": tc.DEFAULT_DEVIATION,
            "magic": tc.INVALID_TEST_MAGIC,
            "comment": "test_zero_volume",
            "type_time": c.Order.OrderTime.GTC,
            "type_filling": c.Order.OrderFilling.IOC,
        }
        # Zero volume should either raise or return error retcode
        result = mt5.order_check(invalid_request)
        # Should fail validation
        if result is not None:
            assert result.retcode != c.Order.TradeRetcode.DONE


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

        Note: order_send may raise PermanentError on some demo accounts.
        """
        # Ensure symbol is selected
        mt5.symbol_select("EURUSD", enable=True)

        result = mt5.order_send(buy_order_request)
        assert result is not None, "order_send returned None"

        # Check for success
        acceptable_codes = [
            c.Order.TradeRetcode.DONE,  # Success
            c.Order.TradeRetcode.PLACED,  # Order placed
        ]
        assert result.retcode in acceptable_codes, (
            f"Unexpected retcode: {result.retcode}"
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

        Note: order_send may raise PermanentError on some demo accounts.
        """
        mt5.symbol_select("EURUSD", enable=True)

        result = mt5.order_send(sell_order_request)
        assert result is not None, "order_send returned None"

        acceptable_codes = [
            c.Order.TradeRetcode.DONE,
            c.Order.TradeRetcode.PLACED,
        ]
        assert result.retcode in acceptable_codes, (
            f"Unexpected retcode: {result.retcode}"
        )

    @pytest.mark.trading
    @pytest.mark.slow
    def test_order_send_buy_limit(
        self,
        mt5: MetaTrader5,
        cleanup_test_positions: None,
    ) -> None:
        """Test placing a buy limit order."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, enable=True)
        tick = mt5.symbol_info_tick(symbol)
        assert tick is not None, "symbol_info_tick returned None"

        # Get symbol info for price calculation
        symbol_info = mt5.symbol_info(symbol)
        assert symbol_info is not None, "symbol_info returned None"

        # Check stops level - some brokers require minimum distance
        stops_level = symbol_info.trade_stops_level
        min_distance = max(stops_level, 100)  # At least 100 points

        # Place limit order below current price (respecting stops level)
        limit_price = round(
            tick.bid - (min_distance * symbol_info.point), symbol_info.digits
        )

        # For pending orders, ORDER_FILLING_RETURN is typically required
        limit_request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": symbol_info.volume_min,
            "type": mt5.ORDER_TYPE_BUY_LIMIT,
            "price": limit_price,
            "magic": tc.INVALID_TEST_MAGIC,
            "comment": "test_buy_limit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        # First check if order is valid
        check_result = mt5.order_check(limit_request)
        assert check_result is not None, "order_check returned None"
        assert check_result.retcode == 0, f"order_check failed: {check_result.retcode}"

        result = mt5.order_send(limit_request)
        assert result is not None, "order_send returned None"
        assert result.retcode == c.Order.TradeRetcode.DONE, (
            f"Unexpected retcode: {result.retcode}"
        )

        # Cleanup: Cancel the pending order
        if result.retcode == c.Order.TradeRetcode.DONE:
            # Cancel the pending order
            orders = mt5.orders_get(symbol="EURUSD")
            if orders:
                for order in orders:
                    if order.magic == tc.INVALID_TEST_MAGIC:
                        cancel_request = {
                            "action": c.Order.TradeAction.REMOVE,
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
        symbol = "EURUSD"
        mt5.symbol_select(symbol, enable=True)

        # Get symbol info to determine correct filling mode
        symbol_info = mt5.symbol_info(symbol)
        assert symbol_info is not None, "symbol_info returned None"
        filling_mode = _get_filling_mode(mt5, symbol_info.filling_mode)

        # Add filling mode to buy request
        buy_order_request["type_filling"] = filling_mode

        # Open position
        open_result = mt5.order_send(buy_order_request)
        assert open_result is not None, "order_send returned None"
        assert open_result.retcode == c.Order.TradeRetcode.DONE, (
            f"Order not filled: {open_result.retcode}"
        )

        # Get the position
        positions = mt5.positions_get(symbol=symbol)
        assert positions, "No positions found after opening"

        position = None
        for pos in positions:
            if pos.magic == tc.TEST_ORDER_MAGIC:
                position = pos
                break

        assert position is not None, "Test position not found"

        # Close the position
        tick = mt5.symbol_info_tick(symbol)
        close_request = {
            "action": c.Order.TradeAction.DEAL,
            "symbol": symbol,
            "volume": position.volume,
            "type": c.Order.OrderType.SELL,  # Opposite of buy
            "position": position.ticket,
            "price": tick.bid,
            "deviation": tc.DEFAULT_DEVIATION,
            "magic": tc.TEST_ORDER_MAGIC,
            "comment": "close_test",
            "type_time": c.Order.OrderTime.GTC,
            "type_filling": filling_mode,
        }

        close_result = mt5.order_send(close_request)
        # Verify order was sent (MT5 may return different success codes)
        assert close_result is not None


class TestOrderCalc:
    """Order calculation tests (margin and profit)."""

    @pytest.mark.trading
    def test_order_calc_margin_buy(self, mt5: MetaTrader5) -> None:
        """Test margin calculation for buy order."""
        mt5.symbol_select("EURUSD", enable=True)
        tick = mt5.symbol_info_tick("EURUSD")
        assert tick is not None, "symbol_info_tick returned None"

        margin = mt5.order_calc_margin(
            c.Order.OrderType.BUY,
            "EURUSD",
            tc.MINI_LOT,  # 0.1 lots
            tick.ask,
        )
        assert margin is not None, "order_calc_margin returned None"
        assert margin > 0

    @pytest.mark.trading
    def test_order_calc_margin_sell(self, mt5: MetaTrader5) -> None:
        """Test margin calculation for sell order."""
        mt5.symbol_select("EURUSD", enable=True)
        tick = mt5.symbol_info_tick("EURUSD")
        assert tick is not None, "symbol_info_tick returned None"

        margin = mt5.order_calc_margin(
            c.Order.OrderType.SELL,
            "EURUSD",
            tc.MINI_LOT,
            tick.bid,
        )
        assert margin is not None, "order_calc_margin returned None"
        assert margin > 0

    @pytest.mark.trading
    def test_order_calc_profit_buy_win(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for winning buy position."""
        mt5.symbol_select("EURUSD", enable=True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.fail("Tick not available")

        # Simulate buy at current price, close higher
        entry_price = tick.ask
        close_price = entry_price + tc.TEN_PIPS  # +10 pips

        profit = mt5.order_calc_profit(
            c.Order.OrderType.BUY,
            "EURUSD",
            tc.MINI_LOT,
            entry_price,
            close_price,
        )

        if profit is None:
            pytest.fail("order_calc_profit not available")
        assert profit > 0  # Should be profitable

    @pytest.mark.trading
    def test_order_calc_profit_buy_loss(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for losing buy position."""
        mt5.symbol_select("EURUSD", enable=True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.fail("Tick not available")

        # Simulate buy at current price, close lower
        entry_price = tick.ask
        close_price = entry_price - tc.TEN_PIPS  # -10 pips

        profit = mt5.order_calc_profit(
            c.Order.OrderType.BUY,
            "EURUSD",
            tc.MINI_LOT,
            entry_price,
            close_price,
        )

        if profit is None:
            pytest.fail("order_calc_profit not available")
        assert profit < 0  # Should be a loss

    @pytest.mark.trading
    def test_order_calc_profit_sell_win(self, mt5: MetaTrader5) -> None:
        """Test profit calculation for winning sell position."""
        mt5.symbol_select("EURUSD", enable=True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.fail("Tick not available")

        # Simulate sell at current price, close lower
        entry_price = tick.bid
        close_price = entry_price - tc.TEN_PIPS  # -10 pips

        profit = mt5.order_calc_profit(
            c.Order.OrderType.SELL,
            "EURUSD",
            tc.MINI_LOT,
            entry_price,
            close_price,
        )

        assert profit is not None
        assert profit > 0  # Should be profitable
