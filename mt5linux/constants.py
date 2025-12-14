"""
MetaTrader 5 constants.

This module contains all MT5 constants organized by category.
These constants are automatically exported to the MetaTrader5 class.
"""

from __future__ import annotations

# =============================================================================
# ACCOUNT CONSTANTS
# =============================================================================

# Account margin modes
ACCOUNT_MARGIN_MODE_RETAIL_NETTING = 0
ACCOUNT_MARGIN_MODE_EXCHANGE = 1
ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2

# Account stopout modes
ACCOUNT_STOPOUT_MODE_PERCENT = 0
ACCOUNT_STOPOUT_MODE_MONEY = 1

# Account trade modes
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2

# =============================================================================
# COPY TICKS CONSTANTS
# =============================================================================

COPY_TICKS_ALL = -1
COPY_TICKS_INFO = 1
COPY_TICKS_TRADE = 2

# =============================================================================
# DAY OF WEEK CONSTANTS
# =============================================================================

DAY_OF_WEEK_SUNDAY = 0
DAY_OF_WEEK_MONDAY = 1
DAY_OF_WEEK_TUESDAY = 2
DAY_OF_WEEK_WEDNESDAY = 3
DAY_OF_WEEK_THURSDAY = 4
DAY_OF_WEEK_FRIDAY = 5
DAY_OF_WEEK_SATURDAY = 6

# =============================================================================
# DEAL CONSTANTS
# =============================================================================

DEAL_DIVIDEND = 15
DEAL_DIVIDEND_FRANKED = 16
DEAL_TAX = 17

# Deal entry types
DEAL_ENTRY_IN = 0
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 2
DEAL_ENTRY_OUT_BY = 3

# Deal reasons
DEAL_REASON_CLIENT = 0
DEAL_REASON_MOBILE = 1
DEAL_REASON_WEB = 2
DEAL_REASON_EXPERT = 3
DEAL_REASON_SL = 4
DEAL_REASON_TP = 5
DEAL_REASON_SO = 6
DEAL_REASON_ROLLOVER = 7
DEAL_REASON_VMARGIN = 8
DEAL_REASON_SPLIT = 9

# Deal types
DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1
DEAL_TYPE_BALANCE = 2
DEAL_TYPE_CREDIT = 3
DEAL_TYPE_CHARGE = 4
DEAL_TYPE_CORRECTION = 5
DEAL_TYPE_BONUS = 6
DEAL_TYPE_COMMISSION = 7
DEAL_TYPE_COMMISSION_DAILY = 8
DEAL_TYPE_COMMISSION_MONTHLY = 9
DEAL_TYPE_COMMISSION_AGENT_DAILY = 10
DEAL_TYPE_COMMISSION_AGENT_MONTHLY = 11
DEAL_TYPE_INTEREST = 12
DEAL_TYPE_BUY_CANCELED = 13
DEAL_TYPE_SELL_CANCELED = 14

# =============================================================================
# ORDER CONSTANTS
# =============================================================================

# Order reasons
ORDER_REASON_CLIENT = 0
ORDER_REASON_MOBILE = 1
ORDER_REASON_WEB = 2
ORDER_REASON_EXPERT = 3
ORDER_REASON_SL = 4
ORDER_REASON_TP = 5
ORDER_REASON_SO = 6

# Order states
ORDER_STATE_STARTED = 0
ORDER_STATE_PLACED = 1
ORDER_STATE_CANCELED = 2
ORDER_STATE_PARTIAL = 3
ORDER_STATE_FILLED = 4
ORDER_STATE_REJECTED = 5
ORDER_STATE_EXPIRED = 6
ORDER_STATE_REQUEST_ADD = 7
ORDER_STATE_REQUEST_MODIFY = 8
ORDER_STATE_REQUEST_CANCEL = 9

# Order types
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5
ORDER_TYPE_BUY_STOP_LIMIT = 6
ORDER_TYPE_SELL_STOP_LIMIT = 7
ORDER_TYPE_CLOSE_BY = 8

# Order filling types
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

# Order time types
ORDER_TIME_GTC = 0
ORDER_TIME_DAY = 1
ORDER_TIME_SPECIFIED = 2
ORDER_TIME_SPECIFIED_DAY = 3

# =============================================================================
# POSITION CONSTANTS
# =============================================================================

# Position reasons
POSITION_REASON_CLIENT = 0
POSITION_REASON_MOBILE = 1
POSITION_REASON_WEB = 2
POSITION_REASON_EXPERT = 3

# Position types
POSITION_TYPE_BUY = 0
POSITION_TYPE_SELL = 1

# =============================================================================
# RESULT CODES
# =============================================================================

RES_E_INTERNAL_FAIL_TIMEOUT = -10005
RES_E_INTERNAL_FAIL_CONNECT = -10004
RES_E_INTERNAL_FAIL_INIT = -10003
RES_E_INTERNAL_FAIL_RECEIVE = -10002
RES_E_INTERNAL_FAIL_SEND = -10001
RES_E_INTERNAL_FAIL = -10000
RES_E_AUTO_TRADING_DISABLED = -8
RES_E_UNSUPPORTED = -7
RES_E_AUTH_FAILED = -6
RES_E_INVALID_VERSION = -5
RES_E_NOT_FOUND = -4
RES_E_NO_MEMORY = -3
RES_E_FAIL = -1
RES_E_INVALID_PARAMS = -2
RES_S_OK = 1

# =============================================================================
# SYMBOL CONSTANTS
# =============================================================================

# Symbol calculation modes
SYMBOL_CALC_MODE_FOREX = 0
SYMBOL_CALC_MODE_FUTURES = 1
SYMBOL_CALC_MODE_CFD = 2
SYMBOL_CALC_MODE_CFDINDEX = 3
SYMBOL_CALC_MODE_CFDLEVERAGE = 4
SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE = 5
SYMBOL_CALC_MODE_EXCH_STOCKS = 32
SYMBOL_CALC_MODE_EXCH_FUTURES = 33
SYMBOL_CALC_MODE_EXCH_OPTIONS = 34
SYMBOL_CALC_MODE_EXCH_OPTIONS_MARGIN = 36
SYMBOL_CALC_MODE_EXCH_BONDS = 37
SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX = 38
SYMBOL_CALC_MODE_EXCH_BONDS_MOEX = 39
SYMBOL_CALC_MODE_SERV_COLLATERAL = 64

# Symbol chart modes
SYMBOL_CHART_MODE_BID = 0
SYMBOL_CHART_MODE_LAST = 1

# Symbol option modes
SYMBOL_OPTION_MODE_EUROPEAN = 0
SYMBOL_OPTION_MODE_AMERICAN = 1

# Symbol option rights
SYMBOL_OPTION_RIGHT_CALL = 0
SYMBOL_OPTION_RIGHT_PUT = 1

# Symbol order modes
SYMBOL_ORDERS_GTC = 0
SYMBOL_ORDERS_DAILY = 1
SYMBOL_ORDERS_DAILY_NO_STOPS = 2

# Symbol swap modes
SYMBOL_SWAP_MODE_DISABLED = 0
SYMBOL_SWAP_MODE_POINTS = 1
SYMBOL_SWAP_MODE_CURRENCY_SYMBOL = 2
SYMBOL_SWAP_MODE_CURRENCY_MARGIN = 3
SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT = 4
SYMBOL_SWAP_MODE_INTEREST_CURRENT = 5
SYMBOL_SWAP_MODE_INTEREST_OPEN = 6
SYMBOL_SWAP_MODE_REOPEN_CURRENT = 7
SYMBOL_SWAP_MODE_REOPEN_BID = 8

# Symbol trade execution modes
SYMBOL_TRADE_EXECUTION_REQUEST = 0
SYMBOL_TRADE_EXECUTION_INSTANT = 1
SYMBOL_TRADE_EXECUTION_MARKET = 2
SYMBOL_TRADE_EXECUTION_EXCHANGE = 3

# Symbol trade modes
SYMBOL_TRADE_MODE_DISABLED = 0
SYMBOL_TRADE_MODE_LONGONLY = 1
SYMBOL_TRADE_MODE_SHORTONLY = 2
SYMBOL_TRADE_MODE_CLOSEONLY = 3
SYMBOL_TRADE_MODE_FULL = 4

# =============================================================================
# TICK CONSTANTS
# =============================================================================

TICK_FLAG_BID = 2
TICK_FLAG_ASK = 4
TICK_FLAG_LAST = 8
TICK_FLAG_VOLUME = 16
TICK_FLAG_BUY = 32
TICK_FLAG_SELL = 64

# =============================================================================
# TIMEFRAME CONSTANTS
# =============================================================================

TIMEFRAME_M1 = 1      # 1 minute
TIMEFRAME_M2 = 2      # 2 minutes
TIMEFRAME_M3 = 3      # 3 minutes
TIMEFRAME_M4 = 4      # 4 minutes
TIMEFRAME_M5 = 5      # 5 minutes
TIMEFRAME_M6 = 6      # 6 minutes
TIMEFRAME_M10 = 10    # 10 minutes
TIMEFRAME_M12 = 12    # 12 minutes
TIMEFRAME_M15 = 15    # 15 minutes
TIMEFRAME_M20 = 20    # 20 minutes
TIMEFRAME_M30 = 30    # 30 minutes
TIMEFRAME_H1 = 16385  # 1 hour
TIMEFRAME_H2 = 16386  # 2 hours
TIMEFRAME_H3 = 16387  # 3 hours
TIMEFRAME_H4 = 16388  # 4 hours
TIMEFRAME_H6 = 16390  # 6 hours
TIMEFRAME_H8 = 16392  # 8 hours
TIMEFRAME_H12 = 16396 # 12 hours
TIMEFRAME_D1 = 16408  # 1 day
TIMEFRAME_W1 = 32769  # 1 week
TIMEFRAME_MN1 = 49153 # 1 month

# =============================================================================
# TRADE RETURN CODES
# =============================================================================

TRADE_RETCODE_REQUOTE = 10004            # Requote
TRADE_RETCODE_REJECT = 10006             # Request rejected
TRADE_RETCODE_CANCEL = 10007             # Request canceled by trader
TRADE_RETCODE_PLACED = 10008             # Order placed
TRADE_RETCODE_DONE = 10009               # Request completed
TRADE_RETCODE_DONE_PARTIAL = 10010       # Only part of the request was completed
TRADE_RETCODE_ERROR = 10011              # Request processing error
TRADE_RETCODE_TIMEOUT = 10012            # Request canceled by timeout
TRADE_RETCODE_INVALID = 10013            # Invalid request
TRADE_RETCODE_INVALID_VOLUME = 10014     # Invalid volume in the request
TRADE_RETCODE_INVALID_PRICE = 10015      # Invalid price in the request
TRADE_RETCODE_INVALID_STOPS = 10016      # Invalid stops in the request
TRADE_RETCODE_TRADE_DISABLED = 10017     # Trade is disabled
TRADE_RETCODE_MARKET_CLOSED = 10018      # Market is closed
TRADE_RETCODE_NO_MONEY = 10019           # Not enough money
TRADE_RETCODE_PRICE_CHANGED = 10020      # Prices changed
TRADE_RETCODE_PRICE_OFF = 10021          # No quotes to process the request
TRADE_RETCODE_INVALID_EXPIRATION = 10022 # Invalid order expiration date
TRADE_RETCODE_ORDER_CHANGED = 10023      # Order state changed
TRADE_RETCODE_TOO_MANY_REQUESTS = 10024  # Too frequent requests
TRADE_RETCODE_NO_CHANGES = 10025         # No changes in request
TRADE_RETCODE_SERVER_DISABLES_AT = 10026 # Autotrading disabled by server
TRADE_RETCODE_CLIENT_DISABLES_AT = 10027 # Autotrading disabled by client terminal
TRADE_RETCODE_LOCKED = 10028             # Request locked for processing
TRADE_RETCODE_FROZEN = 10029             # Order or position frozen
TRADE_RETCODE_INVALID_FILL = 10030       # Invalid order filling type
TRADE_RETCODE_CONNECTION = 10031         # No connection with the trade server
TRADE_RETCODE_ONLY_REAL = 10032          # Operation is allowed only for live accounts
TRADE_RETCODE_LIMIT_ORDERS = 10033       # The number of pending orders has reached the limit
TRADE_RETCODE_LIMIT_VOLUME = 10034       # The volume of orders and positions has reached the limit
TRADE_RETCODE_INVALID_ORDER = 10035      # Incorrect or prohibited order type
TRADE_RETCODE_POSITION_CLOSED = 10036    # Position with the specified POSITION_IDENTIFIER has already been closed
TRADE_RETCODE_INVALID_CLOSE_VOLUME = 10038  # A close volume exceeds the current position volume
TRADE_RETCODE_CLOSE_ORDER_EXIST = 10039  # A close order already exists for a specified position
TRADE_RETCODE_LIMIT_POSITIONS = 10040    # The number of open positions has reached the limit
TRADE_RETCODE_REJECT_CANCEL = 10041      # The pending order activation request is rejected
TRADE_RETCODE_LONG_ONLY = 10042          # Only long positions are allowed
TRADE_RETCODE_SHORT_ONLY = 10043         # Only short positions are allowed
TRADE_RETCODE_CLOSE_ONLY = 10044         # Only position closing is allowed
TRADE_RETCODE_FIFO_CLOSE = 10045         # Position closing is allowed only by FIFO rule
TRADE_RETCODE_HEDGE_PROHIBITED = 10046   # Opposite positions on a single symbol are disabled

# =============================================================================
# TRADE ACTION CONSTANTS
# =============================================================================

TRADE_ACTION_DEAL = 1       # Place an order for an instant deal (market order)
TRADE_ACTION_PENDING = 5    # Place an order for performing a deal at specified conditions (pending order)
TRADE_ACTION_SLTP = 6       # Change open position Stop Loss and Take Profit
TRADE_ACTION_MODIFY = 7     # Change parameters of the previously placed trading order
TRADE_ACTION_REMOVE = 8     # Remove previously placed pending order
TRADE_ACTION_CLOSE_BY = 10  # Close a position by an opposite one

# =============================================================================
# BOOK TYPE CONSTANTS
# =============================================================================

BOOK_TYPE_SELL = 1         # Sell order (Offer)
BOOK_TYPE_BUY = 2          # Buy order (Bid)
BOOK_TYPE_SELL_MARKET = 3  # Sell order by Market
BOOK_TYPE_BUY_MARKET = 4   # Buy order by Market

# =============================================================================
# CONNECTION DEFAULTS
# =============================================================================

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 18812
DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds


# All constants for __all__ export
ALL_CONSTANTS = [
    # Account
    "ACCOUNT_MARGIN_MODE_RETAIL_NETTING",
    "ACCOUNT_MARGIN_MODE_EXCHANGE",
    "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
    "ACCOUNT_STOPOUT_MODE_PERCENT",
    "ACCOUNT_STOPOUT_MODE_MONEY",
    "ACCOUNT_TRADE_MODE_DEMO",
    "ACCOUNT_TRADE_MODE_CONTEST",
    "ACCOUNT_TRADE_MODE_REAL",
    # Copy ticks
    "COPY_TICKS_ALL",
    "COPY_TICKS_INFO",
    "COPY_TICKS_TRADE",
    # Day of week
    "DAY_OF_WEEK_SUNDAY",
    "DAY_OF_WEEK_MONDAY",
    "DAY_OF_WEEK_TUESDAY",
    "DAY_OF_WEEK_WEDNESDAY",
    "DAY_OF_WEEK_THURSDAY",
    "DAY_OF_WEEK_FRIDAY",
    "DAY_OF_WEEK_SATURDAY",
    # Deal
    "DEAL_DIVIDEND",
    "DEAL_DIVIDEND_FRANKED",
    "DEAL_TAX",
    "DEAL_ENTRY_IN",
    "DEAL_ENTRY_OUT",
    "DEAL_ENTRY_INOUT",
    "DEAL_ENTRY_OUT_BY",
    "DEAL_REASON_CLIENT",
    "DEAL_REASON_MOBILE",
    "DEAL_REASON_WEB",
    "DEAL_REASON_EXPERT",
    "DEAL_REASON_SL",
    "DEAL_REASON_TP",
    "DEAL_REASON_SO",
    "DEAL_REASON_ROLLOVER",
    "DEAL_REASON_VMARGIN",
    "DEAL_REASON_SPLIT",
    "DEAL_TYPE_BUY",
    "DEAL_TYPE_SELL",
    "DEAL_TYPE_BALANCE",
    "DEAL_TYPE_CREDIT",
    "DEAL_TYPE_CHARGE",
    "DEAL_TYPE_CORRECTION",
    "DEAL_TYPE_BONUS",
    "DEAL_TYPE_COMMISSION",
    "DEAL_TYPE_COMMISSION_DAILY",
    "DEAL_TYPE_COMMISSION_MONTHLY",
    "DEAL_TYPE_COMMISSION_AGENT_DAILY",
    "DEAL_TYPE_COMMISSION_AGENT_MONTHLY",
    "DEAL_TYPE_INTEREST",
    "DEAL_TYPE_BUY_CANCELED",
    "DEAL_TYPE_SELL_CANCELED",
    # Order
    "ORDER_REASON_CLIENT",
    "ORDER_REASON_MOBILE",
    "ORDER_REASON_WEB",
    "ORDER_REASON_EXPERT",
    "ORDER_REASON_SL",
    "ORDER_REASON_TP",
    "ORDER_REASON_SO",
    "ORDER_STATE_STARTED",
    "ORDER_STATE_PLACED",
    "ORDER_STATE_CANCELED",
    "ORDER_STATE_PARTIAL",
    "ORDER_STATE_FILLED",
    "ORDER_STATE_REJECTED",
    "ORDER_STATE_EXPIRED",
    "ORDER_STATE_REQUEST_ADD",
    "ORDER_STATE_REQUEST_MODIFY",
    "ORDER_STATE_REQUEST_CANCEL",
    "ORDER_TYPE_BUY",
    "ORDER_TYPE_SELL",
    "ORDER_TYPE_BUY_LIMIT",
    "ORDER_TYPE_SELL_LIMIT",
    "ORDER_TYPE_BUY_STOP",
    "ORDER_TYPE_SELL_STOP",
    "ORDER_TYPE_BUY_STOP_LIMIT",
    "ORDER_TYPE_SELL_STOP_LIMIT",
    "ORDER_TYPE_CLOSE_BY",
    "ORDER_FILLING_FOK",
    "ORDER_FILLING_IOC",
    "ORDER_FILLING_RETURN",
    "ORDER_TIME_GTC",
    "ORDER_TIME_DAY",
    "ORDER_TIME_SPECIFIED",
    "ORDER_TIME_SPECIFIED_DAY",
    # Position
    "POSITION_REASON_CLIENT",
    "POSITION_REASON_MOBILE",
    "POSITION_REASON_WEB",
    "POSITION_REASON_EXPERT",
    "POSITION_TYPE_BUY",
    "POSITION_TYPE_SELL",
    # Result codes
    "RES_E_INTERNAL_FAIL_TIMEOUT",
    "RES_E_INTERNAL_FAIL_CONNECT",
    "RES_E_INTERNAL_FAIL_INIT",
    "RES_E_INTERNAL_FAIL_RECEIVE",
    "RES_E_INTERNAL_FAIL_SEND",
    "RES_E_INTERNAL_FAIL",
    "RES_E_AUTO_TRADING_DISABLED",
    "RES_E_UNSUPPORTED",
    "RES_E_AUTH_FAILED",
    "RES_E_INVALID_VERSION",
    "RES_E_NOT_FOUND",
    "RES_E_NO_MEMORY",
    "RES_E_FAIL",
    "RES_E_INVALID_PARAMS",
    "RES_S_OK",
    # Symbol
    "SYMBOL_CALC_MODE_FOREX",
    "SYMBOL_CALC_MODE_FUTURES",
    "SYMBOL_CALC_MODE_CFD",
    "SYMBOL_CALC_MODE_CFDINDEX",
    "SYMBOL_CALC_MODE_CFDLEVERAGE",
    "SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE",
    "SYMBOL_CALC_MODE_EXCH_STOCKS",
    "SYMBOL_CALC_MODE_EXCH_FUTURES",
    "SYMBOL_CALC_MODE_EXCH_OPTIONS",
    "SYMBOL_CALC_MODE_EXCH_OPTIONS_MARGIN",
    "SYMBOL_CALC_MODE_EXCH_BONDS",
    "SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX",
    "SYMBOL_CALC_MODE_EXCH_BONDS_MOEX",
    "SYMBOL_CALC_MODE_SERV_COLLATERAL",
    "SYMBOL_CHART_MODE_BID",
    "SYMBOL_CHART_MODE_LAST",
    "SYMBOL_OPTION_MODE_EUROPEAN",
    "SYMBOL_OPTION_MODE_AMERICAN",
    "SYMBOL_OPTION_RIGHT_CALL",
    "SYMBOL_OPTION_RIGHT_PUT",
    "SYMBOL_ORDERS_GTC",
    "SYMBOL_ORDERS_DAILY",
    "SYMBOL_ORDERS_DAILY_NO_STOPS",
    "SYMBOL_SWAP_MODE_DISABLED",
    "SYMBOL_SWAP_MODE_POINTS",
    "SYMBOL_SWAP_MODE_CURRENCY_SYMBOL",
    "SYMBOL_SWAP_MODE_CURRENCY_MARGIN",
    "SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT",
    "SYMBOL_SWAP_MODE_INTEREST_CURRENT",
    "SYMBOL_SWAP_MODE_INTEREST_OPEN",
    "SYMBOL_SWAP_MODE_REOPEN_CURRENT",
    "SYMBOL_SWAP_MODE_REOPEN_BID",
    "SYMBOL_TRADE_EXECUTION_REQUEST",
    "SYMBOL_TRADE_EXECUTION_INSTANT",
    "SYMBOL_TRADE_EXECUTION_MARKET",
    "SYMBOL_TRADE_EXECUTION_EXCHANGE",
    "SYMBOL_TRADE_MODE_DISABLED",
    "SYMBOL_TRADE_MODE_LONGONLY",
    "SYMBOL_TRADE_MODE_SHORTONLY",
    "SYMBOL_TRADE_MODE_CLOSEONLY",
    "SYMBOL_TRADE_MODE_FULL",
    # Tick
    "TICK_FLAG_BID",
    "TICK_FLAG_ASK",
    "TICK_FLAG_LAST",
    "TICK_FLAG_VOLUME",
    "TICK_FLAG_BUY",
    "TICK_FLAG_SELL",
    # Timeframe
    "TIMEFRAME_M1",
    "TIMEFRAME_M2",
    "TIMEFRAME_M3",
    "TIMEFRAME_M4",
    "TIMEFRAME_M5",
    "TIMEFRAME_M6",
    "TIMEFRAME_M10",
    "TIMEFRAME_M12",
    "TIMEFRAME_M15",
    "TIMEFRAME_M20",
    "TIMEFRAME_M30",
    "TIMEFRAME_H1",
    "TIMEFRAME_H2",
    "TIMEFRAME_H3",
    "TIMEFRAME_H4",
    "TIMEFRAME_H6",
    "TIMEFRAME_H8",
    "TIMEFRAME_H12",
    "TIMEFRAME_D1",
    "TIMEFRAME_W1",
    "TIMEFRAME_MN1",
    # Trade return codes
    "TRADE_RETCODE_REQUOTE",
    "TRADE_RETCODE_REJECT",
    "TRADE_RETCODE_CANCEL",
    "TRADE_RETCODE_PLACED",
    "TRADE_RETCODE_DONE",
    "TRADE_RETCODE_DONE_PARTIAL",
    "TRADE_RETCODE_ERROR",
    "TRADE_RETCODE_TIMEOUT",
    "TRADE_RETCODE_INVALID",
    "TRADE_RETCODE_INVALID_VOLUME",
    "TRADE_RETCODE_INVALID_PRICE",
    "TRADE_RETCODE_INVALID_STOPS",
    "TRADE_RETCODE_TRADE_DISABLED",
    "TRADE_RETCODE_MARKET_CLOSED",
    "TRADE_RETCODE_NO_MONEY",
    "TRADE_RETCODE_PRICE_CHANGED",
    "TRADE_RETCODE_PRICE_OFF",
    "TRADE_RETCODE_INVALID_EXPIRATION",
    "TRADE_RETCODE_ORDER_CHANGED",
    "TRADE_RETCODE_TOO_MANY_REQUESTS",
    "TRADE_RETCODE_NO_CHANGES",
    "TRADE_RETCODE_SERVER_DISABLES_AT",
    "TRADE_RETCODE_CLIENT_DISABLES_AT",
    "TRADE_RETCODE_LOCKED",
    "TRADE_RETCODE_FROZEN",
    "TRADE_RETCODE_INVALID_FILL",
    "TRADE_RETCODE_CONNECTION",
    "TRADE_RETCODE_ONLY_REAL",
    "TRADE_RETCODE_LIMIT_ORDERS",
    "TRADE_RETCODE_LIMIT_VOLUME",
    "TRADE_RETCODE_INVALID_ORDER",
    "TRADE_RETCODE_POSITION_CLOSED",
    "TRADE_RETCODE_INVALID_CLOSE_VOLUME",
    "TRADE_RETCODE_CLOSE_ORDER_EXIST",
    "TRADE_RETCODE_LIMIT_POSITIONS",
    "TRADE_RETCODE_REJECT_CANCEL",
    "TRADE_RETCODE_LONG_ONLY",
    "TRADE_RETCODE_SHORT_ONLY",
    "TRADE_RETCODE_CLOSE_ONLY",
    "TRADE_RETCODE_FIFO_CLOSE",
    "TRADE_RETCODE_HEDGE_PROHIBITED",
    # Trade actions
    "TRADE_ACTION_DEAL",
    "TRADE_ACTION_PENDING",
    "TRADE_ACTION_SLTP",
    "TRADE_ACTION_MODIFY",
    "TRADE_ACTION_REMOVE",
    "TRADE_ACTION_CLOSE_BY",
    # Book types
    "BOOK_TYPE_SELL",
    "BOOK_TYPE_BUY",
    "BOOK_TYPE_SELL_MARKET",
    "BOOK_TYPE_BUY_MARKET",
    # Connection defaults
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT",
    "DEFAULT_RETRY_ATTEMPTS",
    "DEFAULT_RETRY_DELAY",
]
