"""
api_history.py - MetaTrader5 History API for Neptor

# NOTE: This module exceeds 1000 lines due to the need for full API compatibility and extensive
documentation. This exception is justified and documented per Neptor and GEN-AI guidelines.

Provides order, deal, and position history methods compatible with the official MetaTrader5 Python API. Used for historical queries and reporting in the Neptor platform.
"""

# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
# noqa: E501

from typing import Any

import rpyc


class MetaTrader5HistoryAPI:
    """Order, deal, and position history for MetaTrader5."""

    def __init__(self, host: str = 'localhost', port: int = 18812) -> None:
        """

        :param host:  (Default value = 'localhost')
        :type host: str
        :param port:  (Default value = 18812)
        :type port: int
        :rtype: None

        """
        self.__conn: Any = rpyc.classic.connect(host, port)  # type: ignore
        self.__conn._config['sync_request_timeout'] = 300
        self.__conn.execute('import MetaTrader5 as mt5')

    def orders_total(self, *args: object, **kwargs: object) -> Any:
        """Get the number of active orders.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.orders_total(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def orders_get(self, *args: object, **kwargs: object) -> Any:
        r"""# orders_get

        Get active orders with the ability to filter by symbol or ticket. There are three call options.

        Call without parameters. Return active orders on all symbols.

        ```python
        orders_get()
        ```

        Call specifying a symbol active orders should be received for.

        ```python
        orders_get(
            symbol="SYMBOL"      # symbol name
        )
        ```

        Call specifying a group of symbols active orders should be received for.

        ```python
        orders_get(
            group="GROUP"        # filter for selecting orders for symbols
        )
        ```

        Call specifying the order ticket.

        ```python
        orders_get(
        ticket=TICKET        # ticket
        )
        ```

        - symbol="SYMBOL"
            [in]  Symbol name. Optional named parameter. If a symbol is specified, the ticket parameter is ignored.

        - group="GROUP"
            [in]  The filter for arranging a group of necessary symbols. Optional named parameter. If the group is specified, the function returns only active orders meeting a specified criteria for a symbol name.

        - ticket=TICKET
            [in]  Order ticket (ORDER_TICKET). Optional named parameter.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function allows receiving all active orders within one call similar to the OrdersTotal and OrderSelect tandem.

        The group parameter allows sorting out orders by symbols. '*' can be used at the beginning and the end of a string.

        The group parameter may contain several comma separated conditions. A condition can be set as a mask using '*'. The logical negation symbol '!' can be used for an exclusion. All conditions are applied sequentially, which means conditions of including to a group should be specified first followed by an exclusion condition. For example, group="*, !EUR" means that orders for all symbols should be selected first and the ones containing "EUR" in symbol names should be excluded afterwards.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print()
        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # display data on active orders on GBPUSD
        orders=mt5.orders_get(symbol="GBPUSD")
        if orders is None:
            print("No orders on GBPUSD, error code={}".format(mt5.last_error()))
        else:
            print("Total orders on GBPUSD:",len(orders))
            # display all active orders
            for order in orders:
                print(order)
        print()

        # get the list of orders on symbols whose names contain "*GBP*"
        gbp_orders=mt5.orders_get(group="*GBP*")
        if gbp_orders is None:
            print("No orders with group=\"*GBP*\", error code={}".format(mt5.last_error()))
        else:
            print("orders_get(group=\"*GBP*\")={}".format(len(gbp_orders)))
            # display these orders as a table using pandas.DataFrame
            df=pd.DataFrame(list(gbp_orders),columns=gbp_orders[0]._asdict().keys())
            df.drop(['time_done', 'time_done_msc', 'position_id', 'position_by_id', 'reason', 'volume_initial', 'price_stoplimit'], axis=1, inplace=True)
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Total orders on GBPUSD: 2
        TradeOrder(ticket=554733548, time_setup=1585153667, time_setup_msc=1585153667718, time_done=0, time_done_msc=0, time_expiration=0, type=3, type_time=0, ...
        TradeOrder(ticket=554733621, time_setup=1585153671, time_setup_msc=1585153671419, time_done=0, time_done_msc=0, time_expiration=0, type=2, type_time=0, ...

        orders_get(group="*GBP*")=4
            ticket          time_setup  time_setup_msc  time_expiration  type  type_time  type_filling  state  magic  volume_current  price_open   sl   tp  price_current  symbol comment external_id
        0  554733548 2020-03-25 16:27:47   1585153667718                0     3          0             2      1      0             0.2     1.25379  0.0  0.0        1.16803  GBPUSD
        1  554733621 2020-03-25 16:27:51   1585153671419                0     2          0             2      1      0             0.2     1.14370  0.0  0.0        1.16815  GBPUSD
        2  554746664 2020-03-25 16:38:14   1585154294401                0     3          0             2      1      0             0.2     0.93851  0.0  0.0        0.92428  EURGBP
        3  554746710 2020-03-25 16:38:17   1585154297022                0     2          0             2      1      0             0.2     0.90527  0.0  0.0        0.92449  EURGBP
        ```

        ## See also
            `orders_total`, `positions_get`
        :rtype: Any

        """
        code = f'mt5.orders_get(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def order_calc_margin(self, *args: object, **kwargs: object) -> Any:
        r"""# order_calc_margin

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ```python
        order_calc_margin(
            action,      # order type (ORDER_TYPE_BUY or ORDER_TYPE_SELL)
            symbol,      # symbol name
            volume,      # volume
            price        # open price
            )
        ```

        ## Parameters

        - action

            [in]  Order type taking values from the `ORDER_TYPE` enumeration. Required unnamed parameter.

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        - volume

            [in]  Trading operation volume. Required unnamed parameter.

        - price

            [in]  Open price. Required unnamed parameter.

        ## Return Value

        Real value if successful, otherwise None. The error info can be obtained using `last_error()`.

        ## Note

        The function allows estimating the margin necessary for a specified order type on the current account and in the current market environment without considering the current pending orders and open positions. The function is similar to `OrderCalcMargin`.

        | ID                         | Description                                                                          |
        |----------------------------|--------------------------------------------------------------------------------------|
        | ORDER_TYPE_BUY             | Market buy order                                                                     |
        | ORDER_TYPE_SELL            | Market sell order                                                                    |
        | ORDER_TYPE_BUY_LIMIT       | Buy Limit pending order                                                              |
        | ORDER_TYPE_SELL_LIMIT      | Sell Limit pending order                                                             |
        | ORDER_TYPE_BUY_STOP        | Buy Stop pending order                                                               |
        | ORDER_TYPE_SELL_STOP       | Sell Stop pending order                                                              |
        | ORDER_TYPE_BUY_STOP_LIMIT  | Upon reaching the order price, Buy Limit pending order is placed at StopLimit price  |
        | ORDER_TYPE_SELL_STOP_LIMIT | Upon reaching the order price, Sell Limit pending order is placed at StopLimit price |
        | ORDER_TYPE_CLOSE_BY        | Order for closing a position by an opposite one                                      |

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get account currency
        account_currency=mt5.account_info().currency
        print("Account сurrency:",account_currency)

        # arrange the symbol list
        symbols=("EURUSD","GBPUSD","USDJPY", "USDCHF","EURJPY","GBPJPY")
        print("Symbols to check margin:", symbols)
        action=mt5.ORDER_TYPE_BUY
        lot=0.1
        for symbol in symbols:
            symbol_info=mt5.symbol_info(symbol)
            if symbol_info is None:
                print(symbol,"not found, skipped")
                continue
            if not symbol_info.visible:
                print(symbol, "is not visible, trying to switch on")
                if not mt5.symbol_select(symbol,True):
                    print("symbol_select({}}) failed, skipped",symbol)
                    continue
            ask=mt5.symbol_info_tick(symbol).ask
            margin=mt5.order_calc_margin(action,symbol,lot,ask)
            if margin != None:
                print("   {} buy {} lot margin: {} {}".format(symbol,lot,margin,account_currency));
            else:
                print("order_calc_margin failed: , error code =", mt5.last_error())

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Account сurrency: USD

        Symbols to check margin: ('EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'EURJPY', 'GBPJPY')
            EURUSD buy 0.1 lot margin: 109.91 USD
            GBPUSD buy 0.1 lot margin: 122.73 USD
            USDJPY buy 0.1 lot margin: 100.0 USD
            USDCHF buy 0.1 lot margin: 100.0 USD
            EURJPY buy 0.1 lot margin: 109.91 USD
            GBPJPY buy 0.1 lot margin: 122.73 USD
        ```
        ## See also
            `order_calc_profit`, `order_check`
        :rtype: Any

        """
        code = f'mt5.order_calc_margin(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def order_calc_profit(self, *args: object, **kwargs: object) -> Any:
        r"""# order_calc_profit

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ```python
        order_calc_profit(
            action,          # order type (ORDER_TYPE_BUY or ORDER_TYPE_SELL)
            symbol,          # symbol name
            volume,          # volume
            price_open,      # open price
            price_close      # close price
            );
        ```

        ## Parameters

        - action

            [in]  Order type may take one of the two `ORDER_TYPE` enumeration values: `ORDER_TYPE_BUY` or `ORDER_TYPE_SELL`. Required unnamed parameter.

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        - volume

            [in]  Trading operation volume. Required unnamed parameter.

        - price_open

            [in]  Open price. Required unnamed parameter.

        - price_close

            [in]  Close price. Required unnamed parameter.

        ## Return Value

        Real value if successful, otherwise None. The error info can be obtained using `last_error()`.

        ## Note

        The function allows estimating a trading operation result on the current account and in the current trading environment. The function is similar to `OrderCalcProfit`.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get account currency
        account_currency=mt5.account_info().currency
        print("Account сurrency:",account_currency)

        # arrange the symbol list
        symbols = ("EURUSD","GBPUSD","USDJPY")
        print("Symbols to check margin:", symbols)
        # estimate profit for buying and selling
        lot=1.0
        distance=300
        for symbol in symbols:
            symbol_info=mt5.symbol_info(symbol)
            if symbol_info is None:
                print(symbol,"not found, skipped")
                continue
            if not symbol_info.visible:
                print(symbol, "is not visible, trying to switch on")
                if not mt5.symbol_select(symbol,True):
                    print("symbol_select({}}) failed, skipped",symbol)
                    continue
            point=mt5.symbol_info(symbol).point
            symbol_tick=mt5.symbol_info_tick(symbol)
            ask=symbol_tick.ask
            bid=symbol_tick.bid
            buy_profit=mt5.order_calc_profit(mt5.ORDER_TYPE_BUY,symbol,lot,ask,ask+distance*point)
            if buy_profit!=None:
                print("   buy {} {} lot: profit on {} points => {} {}".format(symbol,lot,distance,buy_profit,account_currency));
            else:
                print("order_calc_profit(ORDER_TYPE_BUY) failed, error code =",mt5.last_error())
            sell_profit=mt5.order_calc_profit(mt5.ORDER_TYPE_SELL,symbol,lot,bid,bid-distance*point)
            if sell_profit!=None:
                print("   sell {} {} lots: profit on {} points => {} {}".format(symbol,lot,distance,sell_profit,account_currency));
            else:
                print("order_calc_profit(ORDER_TYPE_SELL) failed, error code =",mt5.last_error())
            print()

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Account сurrency: USD
        Symbols to check margin: ('EURUSD', 'GBPUSD', 'USDJPY')
            buy EURUSD 1.0 lot: profit on 300 points => 300.0 USD
            sell EURUSD 1.0 lot: profit on 300 points => 300.0 USD

            buy GBPUSD 1.0 lot: profit on 300 points => 300.0 USD
            sell GBPUSD 1.0 lot: profit on 300 points => 300.0 USD

            buy USDJPY 1.0 lot: profit on 300 points => 276.54 USD
            sell USDJPY 1.0 lot: profit on 300 points => 278.09 USD
        ```

        ## See also

            `order_calc_margin`, `order_check`
        :rtype: Any

        """
        code = f'mt5.order_calc_profit(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def order_check(self, *args: object, **kwargs: object) -> Any:
        r"""# order_check

        Check funds sufficiency for performing a required trading operation. Check result are returned as the MqlTradeCheckResult structure.

        ```python
        order_check(
        request      # request structure
        );
        ```

        ## Parameters

        - request

            [in] MqlTradeRequest type structure describing a required trading action. Required unnamed parameter. Example of filling in a request and the enumeration content are described below.

        ## Return Value

        Check result as the `MqlTradeCheckResult` structure. The request field in the answer contains the structure of a trading request passed to `order_check()`.

        ## Note

        Successful sending of a request does not entail that the requested trading operation will be executed successfully. The order_check function is similar to `OrderCheck`.

        ### TRADE_REQUEST_ACTIONS

        | ID                    | Description                                                                           |
        |-----------------------|---------------------------------------------------------------------------------------|
        | TRADE_ACTION_DEAL     | Place an order for an instant deal with the specified parameters (set a market order) |
        | TRADE_ACTION_PENDING  | Place an order for performing a deal at specified conditions (pending order)          |
        | TRADE_ACTION_SLTP     | Change open position Stop Loss and Take Profit                                        |
        | TRADE_ACTION_MODIFY   | Change parameters of the previously placed trading order                              |
        | TRADE_ACTION_REMOVE   | Remove previously placed pending order                                                |
        | TRADE_ACTION_CLOSE_BY | Close a position by an opposite one                                                   |

        ### ORDER_TYPE_FILLING

        | ID                   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
        |----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
        | ORDER_FILLING_FOK    | This execution policy means that an order can be executed only in the specified volume. If the necessary amount of a financial instrument is currently unavailable in the market, the order will not be executed. The desired volume can be made up of several available offers.                                                                                                                                                                                                                                                                                                                                 |
        | ORDER_FILLING_IOC    | An agreement to execute a deal at the maximum volume available in the market within the volume specified in the order. If the request cannot be filled completely, an order with the available volume will be executed, and the remaining volume will be canceled.                                                                                                                                                                                                                                                                                                                                               |
        | ORDER_FILLING_RETURN | This policy is used only for market (ORDER_TYPE_BUY and ORDER_TYPE_SELL), limit and stop limit orders (ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT, ORDER_TYPE_BUY_STOP_LIMIT and ORDER_TYPE_SELL_STOP_LIMIT) and only for the symbols with Market or Exchange execution modes. If filled partially, a market or limit order with the remaining volume is not canceled, and is processed further. During activation of the ORDER_TYPE_BUY_STOP_LIMIT and ORDER_TYPE_SELL_STOP_LIMIT orders, an appropriate limit order ORDER_TYPE_BUY_LIMIT/ORDER_TYPE_SELL_LIMIT with the ORDER_FILLING_RETURN type is created. |

        ### ORDER_TYPE_TIME

        | ID                       | Description                                                                                                                                                            |
        |--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
        | ORDER_TIME_GTC           | The order stays in the queue until it is manually canceled                                                                                                             |
        | ORDER_TIME_DAY           | The order is active only during the current trading day                                                                                                                |
        | ORDER_TIME_SPECIFIED     | The order is active until the specified date                                                                                                                           |
        | ORDER_TIME_SPECIFIED_DAY | The order is active until 23:59:59 of the specified day. If this time appears to be out of a trading session, the expiration is processed at the nearest trading time. |

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get account currency
        account_currency=mt5.account_info().currency
        print("Account сurrency:",account_currency)

        # prepare the request structure
        symbol="USDJPY"
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # if the symbol is unavailable in MarketWatch, add it
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)
                mt5.shutdown()
                quit()

        # prepare the request
        point=mt5.symbol_info(symbol).point
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 1.0,
            "type": mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(symbol).ask,
            "sl": mt5.symbol_info_tick(symbol).ask-100*point,
            "tp": mt5.symbol_info_tick(symbol).ask+100*point,
            "deviation": 10,
            "magic": 234000,
            "comment": "python script",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        # perform the check and display the result 'as is'
        result = mt5.order_check(request)
        print(result);
        # request the result as a dictionary and display it element by element
        result_dict=result._asdict()
        for field in result_dict.keys():
            print("   {}={}".format(field,result_dict[field]))
            # if this is a trading request structure, display it element by element as well
            if field=="request":
                traderequest_dict=result_dict[field]._asdict()
                for tradereq_filed in traderequest_dict:
                    print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Account сurrency: USD
        retcode=0
        balance=101300.53
        equity=68319.53
        profit=-32981.0
        margin=51193.67
        margin_free=17125.86
        margin_level=133.45308121101692
        comment=Done
        request=TradeRequest(action=1, magic=234000, order=0, symbol='USDJPY', volume=1.0, ...
            traderequest: action=1
            traderequest: magic=234000
            traderequest: order=0
            traderequest: symbol=USDJPY
            traderequest: volume=1.0
            traderequest: price=108.081
            traderequest: stoplimit=0.0
            traderequest: sl=107.98100000000001
            traderequest: tp=108.181
            traderequest: deviation=10
            traderequest: type=0
            traderequest: type_filling=2
            traderequest: type_time=0
            traderequest: expiration=0
            traderequest: comment=python script
            traderequest: position=0
            traderequest: position_by=0
        ```

        ## See also
            `order_send`, `OrderCheck`, Trading operation types, Trading request structure, Structure of the trading request check results, Structure of the trading request result

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.order_check(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def order_send(self, request: object) -> Any:
        r"""# order_send

        Send a request to perform a trading operation from the terminal to the trade server. The function is similar to OrderSend.

        ```python
        order_send(
        request      # request structure
        );
        ```

        ## Parameters

        request

            [in] `MqlTradeRequest` type structure describing a required trading action. Required unnamed parameter. Example of filling in a request and the enumeration content are described below.

        ## Return Value

        Execution result as the `MqlTradeResult` structure. The request field in the answer contains the structure of a trading request passed to `order_send()`.

        The `MqlTradeRequest` trading request structure

        | Field        | Description                                                                                                                                                                                                |
        |--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
        | action       | Trading operation type. The value can be one of the values of the TRADE_REQUEST_ACTIONS enumeration                                                                                                        |
        | magic        | EA ID. Allows arranging the analytical handling of trading orders. Each EA can set a unique ID when sending a trading request                                                                              |
        | order        | Order ticket. Required for modifying pending orders                                                                                                                                                        |
        | symbol       | The name of the trading instrument, for which the order is placed. Not required when modifying orders and closing positions                                                                                |
        | volume       | Requested volume of a deal in lots. A real volume when making a deal depends on an order execution type.                                                                                                   |
        | price        | Price at which an order should be executed. The price is not set in case of market orders for instruments of the "Market Execution" (SYMBOL_TRADE_EXECUTION_MARKET) type having the TRADE_ACTION_DEAL type |
        | stoplimit    | A price a pending Limit order is set at when the price reaches the 'price' value (this condition is mandatory). The pending order is not passed to the trading system until that moment                    |
        | sl           | A price a Stop Loss order is activated at when the price moves in an unfavorable direction                                                                                                                 |
        | tp           | A price a Take Profit order is activated at when the price moves in a favorable direction                                                                                                                  |
        | deviation    | Maximum acceptable deviation from the requested price, specified in points                                                                                                                                 |
        | type         | Order type. The value can be one of the values of the ORDER_TYPE enumeration                                                                                                                               |
        | type_filling | Order filling type. The value can be one of the ORDER_TYPE_FILLING values                                                                                                                              |
        | type_time    | Order type by expiration. The value can be one of the ORDER_TYPE_TIME values                                                                                                                               |
        | expiration   | Pending order expiration time (for TIME_SPECIFIED type orders)                                                                                                                                             |
        | comment      | Comment to an order                                                                                                                                                                                        |
        | position     | Position ticket. Fill it when changing and closing a position for its clear identification. Usually, it is the same as the ticket of the order that opened the position.                                   |
        | position_by  | Opposite position ticket. It is used when closing a position by an opposite one (opened at the same symbol but in the opposite direction).                                                                 |

        ## Note

        A trading request passes several verification stages on the trade server. First, the validity of all the necessary request fields is checked. If there are no errors, the server accepts the order for further handling. See the OrderSend function description for the details about executing trading operations.

        ## Example:

        ```python
        import time
        import MetaTrader5 as mt5

        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ", mt5.__author__)
        print("MetaTrader5 package version: ", mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # prepare the buy request structure
        symbol = "USDJPY"
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()

        # if the symbol is unavailable in MarketWatch, add it
        if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)
                mt5.shutdown()
                quit()

        lot = 0.1
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask
        deviation = 20
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": price - 100 * point,
            "tp": price + 100 * point,
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        # send a trading request
        result = mt5.order_send(request)
        # check the execution result
        print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol,lot,price,deviation));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # request the result as a dictionary and display it element by element
            result_dict=result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field,result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field=="request":
                    traderequest_dict=result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))
            print("shutdown() and quit")
            mt5.shutdown()
            quit()

        print("2. order_send done, ", result)
        print("   opened position with POSITION_TICKET={}".format(result.order))
        print("   sleep 2 seconds before closing position #{}".format(result.order))
        time.sleep(2)
        # create a close request
        position_id=result.order
        price=mt5.symbol_info_tick(symbol).bid
        deviation=20
        request={
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "position": position_id,
            "price": price,
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        # send a trading request
        result=mt5.order_send(request)
        # check the execution result
        print("3. close position #{}: sell {} {} lots at {} with deviation={} points".format(position_id,symbol,lot,price,deviation));
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("4. order_send failed, retcode={}".format(result.retcode))
            print("   result",result)
        else:
            print("4. position #{} closed, {}".format(position_id,result))
            # request the result as a dictionary and display it element by element
            result_dict=result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field,result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field=="request":
                    traderequest_dict=result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        # Result

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        1. order_send(): by USDJPY 0.1 lots at 108.023 with deviation=20 points
        2. order_send done,  OrderSendResult(retcode=10009, deal=535084512, order=557416535, volume=0.1, price=108.023, ...
        opened position with POSITION_TICKET=557416535
        sleep 2 seconds before closing position #557416535
        3. close position #557416535: sell USDJPY 0.1 lots at 108.018 with deviation=20 points
        4. position #557416535 closed, OrderSendResult(retcode=10009, deal=535084631, order=557416654, volume=0.1, price=...
        retcode=10009
        deal=535084631
        order=557416654
        volume=0.1
        price=108.015
        bid=108.015
        ask=108.02
        comment=Request executed
        request_id=55
        retcode_external=0
        request=TradeRequest(action=1, magic=234000, order=0, symbol='USDJPY', volume=0.1, price=108.018, stoplimit=0.0, ...
            traderequest: action=1
            traderequest: magic=234000
            traderequest: order=0
            traderequest: symbol=USDJPY
            traderequest: volume=0.1
            traderequest: price=108.018
            traderequest: stoplimit=0.0
            traderequest: sl=0.0
            traderequest: tp=0.0
            traderequest: deviation=20
            traderequest: type=1
            traderequest: type_filling=2
            traderequest: type_time=0
            traderequest: expiration=0
            traderequest: comment=python script close
            traderequest: position=557416535
            traderequest: position_by=0
        ```

        ## See also

            `order_check`, `OrderSend`,Trading operation types, Trading request structure, Structure of the trading request check results, Structure of the trading request result

        :param request: 
        :type request: object
        :rtype: Any

        """
        code = f'mt5.order_send({request})'
        return self.__conn.eval(code)

    def positions_total(self, *args: object, **kwargs: object) -> Any:
        r"""# positions_total

        Get the number of open positions.

        ```python
        positions_total()
        ```

        ## Return Value

        Integer value.

        ## Note

        The function is similar to `PositionsTotal`.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # check the presence of open positions
        positions_total=mt5.positions_total()
        if positions_total>0:
            print("Total positions=",positions_total)
        else:
            print("Positions not found")

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `positions_get`, `orders_total`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.positions_total(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def positions_get(self, *args: object, **kwargs: object) -> Any:
        r"""# positions_get

        Get open positions with the ability to filter by symbol or ticket. There are three call options.

        Call without parameters. Return open positions for all symbols.

        ```python
        positions_get()
        ```

        Call specifying a symbol open positions should be received for.

        ```python
        positions_get(
        symbol="SYMBOL"      # symbol name
        )
        ```

        Call specifying a group of symbols open positions should be received for.

        ```python
        positions_get(
        group="GROUP"        # filter for selecting positions by symbols
        )
        ```

        Call specifying a position ticket.

        ```python
        positions_get(
        ticket=TICKET        # ticket
        )
        ```

        ## Parameters

        - symbol="SYMBOL"

            [in]  Symbol name. Optional named parameter. If a symbol is specified, the ticket parameter is ignored.

        - group="GROUP"

            [in]  The filter for arranging a group of necessary symbols. Optional named parameter. If the group is specified, the function returns only positions meeting a specified criteria for a symbol name.

        - ticket=TICKET

            [in]  Position ticket (`POSITION_TICKET`). Optional named parameter.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function allows receiving all open positions within one call similar to the `PositionsTotal` and `PositionSelect` tandem.

        The group parameter may contain several comma separated conditions. A condition can be set as a mask using '*'. The logical negation symbol '!' can be used for an exclusion. All conditions are applied sequentially, which means conditions of including to a group should be specified first followed by an exclusion condition. For example, group="*, !EUR" means that positions for all symbols should be selected first and the ones containing "EUR" in symbol names should be excluded afterwards.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print()
        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get open positions on USDCHF
        positions=mt5.positions_get(symbol="USDCHF")
        if positions==None:
            print("No positions on USDCHF, error code={}".format(mt5.last_error()))
        elif len(positions)>0:
            print("Total positions on USDCHF =",len(positions))
            # display all open positions
            for position in positions:
                print(position)

        # get the list of positions on symbols whose names contain "*USD*"
        usd_positions=mt5.positions_get(group="*USD*")
        if usd_positions==None:
            print("No positions with group=\"*USD*\", error code={}".format(mt5.last_error()))
        elif len(usd_positions)>0:
            print("positions_get(group=\"*USD*\")={}".format(len(usd_positions)))
            # display these positions as a table using pandas.DataFrame
            df=pd.DataFrame(list(usd_positions),columns=usd_positions[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        positions_get(group="*USD*")=5
            ticket                time  type  magic  identifier  reason  volume  price_open       sl       tp  price_current  swap  profit  symbol comment
        0  548297723 2020-03-18 15:00:55     1      0   548297723       3    0.01     1.09301  1.11490  1.06236        1.10104 -0.10   -8.03  EURUSD
        1  548655158 2020-03-18 20:31:26     0      0   548655158       3    0.01     1.08676  1.06107  1.12446        1.10099 -0.08   14.23  EURUSD
        2  548663803 2020-03-18 20:40:04     0      0   548663803       3    0.01     1.08640  1.06351  1.11833        1.10099 -0.08   14.59  EURUSD
        3  548847168 2020-03-19 01:10:05     0      0   548847168       3    0.01     1.09545  1.05524  1.15122        1.10099 -0.06    5.54  EURUSD
        4  548847194 2020-03-19 01:10:07     0      0   548847194       3    0.02     1.09536  1.04478  1.16587        1.10099 -0.08   11.26  EURUSD
        ```

        ## See also

            `positions_total`, `orders_get`
        :rtype: Any

        """
        code = f'mt5.positions_get(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def history_orders_total(self, date_from: object, date_to: object) -> Any:
        r"""# history_orders_total

        Get the number of orders in trading history within the specified interval.

        ```python
        history_orders_total(
        date_from,    # date the orders are requested from
        date_to       # date, up to which the orders are requested
        )
        ```

        ## Parameters

        - date_from

            [in]  Date the orders are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - date_to

            [in]  Date, up to which the orders are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        ## Return Value

        Integer value.

        ## Note

        The function is similar to `HistoryOrdersTotal`.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get the number of orders in history
        from_date=datetime(2020,1,1)
        to_date=datetime.now()
        history_orders=mt5.history_orders_total(from_date, datetime.now())
        if history_orders>0:
            print("Total history orders=",history_orders)
        else:
            print("Orders not found in history")

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `history_orders_get`, `history_deals_total`

        :param date_from: 
        :type date_from: object
        :param date_to: 
        :type date_to: object
        :rtype: Any

        """
        code = f'mt5.history_orders_total({repr(date_from)}, {repr(date_to)})'
        return self.__conn.eval(code)

    def history_orders_get(self, *args: object, **kwargs: object) -> Any:
        r"""#history_orders_get

        Get orders from trading history with the ability to filter by ticket or position. There are three call options.

        Call specifying a time interval. Return all orders falling within the specified interval.

        ```python
        history_orders_get(
        date_from,                # date the orders are requested from
        date_to,                  # date, up to which the orders are requested
        group="GROUP"        # filter for selecting orders by symbols
        )
        ```

        Call specifying the order ticket. Return an order with the specified ticket.

        ```python
        positions_get(
        ticket=TICKET        # order ticket
        )
        ```

        Call specifying the position ticket. Return all orders with a position ticket specified in the ORDER_POSITION_ID property.

        ```python
        positions_get(
        position=POSITION    # position ticket
        )
        ```

        ## Parameters

        - date_from

            [in]  Date the orders are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter is specified first.

        - date_to

            [in]  Date, up to which the orders are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter is specified second.

        - group="GROUP"

            [in]  The filter for arranging a group of necessary symbols. Optional named parameter. If the group is specified, the function returns only orders meeting a specified criteria for a symbol name.

        - ticket=TICKET

            [in]  Order ticket that should be received. Optional parameter. If not specified, the filter is not applied.

        - position=POSITION

            [in]  Ticket of a position (stored in `ORDER_POSITION_ID`) all orders should be received for. Optional parameter. If not specified, the filter is not applied.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function allows receiving all history orders within a specified period in a single call similar to the HistoryOrdersTotal and HistoryOrderSelect tandem.

        The group parameter may contain several comma separated conditions. A condition can be set as a mask using '*'. The logical negation symbol '!' can be used for an exclusion. All conditions are applied sequentially, which means conditions of including to a group should be specified first followed by an exclusion condition. For example, group="*, !EUR" means that deals for all symbols should be selected first and the ones containing "EUR" in symbol names should be excluded afterwards.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print()
        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get the number of orders in history
        from_date=datetime(2020,1,1)
        to_date=datetime.now()
        history_orders=mt5.history_orders_get(from_date, to_date, group="*GBP*")
        if history_orders==None:
            print("No history orders with group=\"*GBP*\", error code={}".format(mt5.last_error()))
        elif len(history_orders)>0:
            print("history_orders_get({}, {}, group=\"*GBP*\")={}".format(from_date,to_date,len(history_orders)))
        print()

        # display all historical orders by a position ticket
        position_id=530218319
        position_history_orders=mt5.history_orders_get(position=position_id)
        if position_history_orders==None:
            print("No orders with position #{}".format(position_id))
            print("error code =",mt5.last_error())
        elif len(position_history_orders)>0:
            print("Total history orders on position #{}: {}".format(position_id,len(position_history_orders)))
            # display all historical orders having a specified position ticket
            for position_order in position_history_orders:
                print(position_order)
            print()
            # display these orders as a table using pandas.DataFrame
            df=pd.DataFrame(list(position_history_orders),columns=position_history_orders[0]._asdict().keys())
            df.drop(['time_expiration','type_time','state','position_by_id','reason','volume_current','price_stoplimit','sl','tp'], axis=1, inplace=True)
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            df['time_done'] = pd.to_datetime(df['time_done'], unit='s')
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        history_orders_get(2020-01-01 00:00:00, 2020-03-25 17:17:32.058795, group="*GBP*")=14

        Total history orders on position #530218319: 2
        TradeOrder(ticket=530218319, time_setup=1582282114, time_setup_msc=1582282114681, time_done=1582303777, time_done_msc=1582303777582, time_expiration=0, ...
        TradeOrder(ticket=535548147, time_setup=1583176242, time_setup_msc=1583176242265, time_done=1583176242, time_done_msc=1583176242265, time_expiration=0, ...

            ticket          time_setup  time_setup_msc           time_done  time_done_msc  type  type_filling  magic  position_id  volume_initial  price_open  price_current  symbol comment external_id
        0  530218319 2020-02-21 10:48:34   1582282114681 2020-02-21 16:49:37  1582303777582     2             2      0    530218319            0.01     0.97898        0.97863  USDCHF
        1  535548147 2020-03-02 19:10:42   1583176242265 2020-03-02 19:10:42  1583176242265     1             0      0    530218319            0.01     0.95758        0.95758  USDCHF
        ```

        ## See also

            `history_deals_total`, `history_deals_get`
        :rtype: Any

        """
        code = f'mt5.history_orders_get(*{args},**{kwargs})'
        response = self.__conn.eval(code)
        return response

    def history_deals_total(self, date_from: object, date_to: object) -> Any:
        r"""# history_deals_total

        Get the number of deals in trading history within the specified interval.

        ```python
        history_deals_total(
        date_from,    # date the deals are requested from
        date_to       # date, up to which the deals are requested
        )
        ```

        ## Parameters

        - date_from

            [in]  Date the deals are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - date_to

            [in]  Date, up to which the deals are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        ## Return Value

        Integer value.

        ## Note

        The function is similar to `HistoryDealsTotal`.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get the number of deals in history
        from_date=datetime(2020,1,1)
        to_date=datetime.now()
        deals=mt5.history_deals_total(from_date, to_date)
        if deals>0:
            print("Total deals=",deals)
        else:
            print("Deals not found in history")

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `history_deals_get`, `history_orders_total`

        :param date_from: 
        :type date_from: object
        :param date_to: 
        :type date_to: object
        :rtype: Any

        """
        code = f'mt5.history_deals_total({repr(date_from)}, {repr(date_to)})'
        return self.__conn.eval(code)

    def history_deals_get(self, *args: object, **kwargs: object) -> Any:
        r"""#history_deals_get

        Get deals from trading history within the specified interval with the ability to filter by ticket or position.

        Call specifying a time interval. Return all deals falling within the specified interval.

        ```python
        history_deals_get(
        date_from,                # date the deals are requested from
        date_to,                  # date, up to which the deals are requested
        group="GROUP"        # filter for selecting deals for symbols
        )
        ```

        Call specifying the order ticket. Return all deals having the specified order ticket in the DEAL_ORDER property.

        ```python
        history_deals_get(
        ticket=TICKET        # order ticket
        )
        ```

        Call specifying the position ticket. Return all deals having the specified position ticket in the DEAL_POSITION_ID property.

        ```python
        history_deals_get(
        position=POSITION    # position ticket
        )
        ```

        ## Parameters

        - date_from

            [in]  Date the orders are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter is specified first.

        - date_to

            [in]  Date, up to which the orders are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter is specified second.

        - group="GROUP"

            [in]  The filter for arranging a group of necessary symbols. Optional named parameter. If the group is specified, the function returns only deals meeting a specified criteria for a symbol name.

        - ticket=TICKET

            [in]  Ticket of an order (stored in `DEAL_ORDER`) all deals should be received for. Optional parameter. If not specified, the filter is not applied.

        - position=POSITION

            [in]  Ticket of a position (stored in `DEAL_POSITION_ID`) all deals should be received for. Optional parameter. If not specified, the filter is not applied.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function allows receiving all history deals within a specified period in a single call similar to the HistoryDealsTotal and `HistoryDealSelect` tandem.

        The group parameter allows sorting out deals by symbols. '*' can be used at the beginning and the end of a string.

        The group parameter may contain several comma separated conditions. A condition can be set as a mask using '*'. The logical negation symbol '!' can be used for an exclusion. All conditions are applied sequentially, which means conditions of including to a group should be specified first followed by an exclusion condition. For example, group="*, !EUR" means that deals for all symbols should be selected first and the ones containing "EUR" in symbol names should be excluded afterwards.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        from datetime import datetime
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print()
        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get the number of deals in history
        from_date=datetime(2020,1,1)
        to_date=datetime.now()
        # get deals for symbols whose names contain "GBP" within a specified interval
        deals=mt5.history_deals_get(from_date, to_date, group="*GBP*")
        if deals==None:
            print("No deals with group=\"*USD*\", error code={}".format(mt5.last_error()))
        elif len(deals)> 0:
            print("history_deals_get({}, {}, group=\"*GBP*\")={}".format(from_date,to_date,len(deals)))

        # get deals for symbols whose names contain neither "EUR" nor "GBP"
        deals = mt5.history_deals_get(from_date, to_date, group="*,!*EUR*,!*GBP*")
        if deals == None:
            print("No deals, error code={}".format(mt5.last_error()))
        elif len(deals) > 0:
            print("history_deals_get(from_date, to_date, group=\"*,!*EUR*,!*GBP*\") =", len(deals))
            # display all obtained deals 'as is'
            for deal in deals:
                print("  ",deal)
            print()
            # display these deals as a table using pandas.DataFrame
            df=pd.DataFrame(list(deals),columns=deals[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            print(df)
        print("")

        # get all deals related to the position #530218319
        position_id=530218319
        position_deals = mt5.history_deals_get(position=position_id)
        if position_deals == None:
            print("No deals with position #{}".format(position_id))
            print("error code =", mt5.last_error())
        elif len(position_deals) > 0:
            print("Deals with position id #{}: {}".format(position_id, len(position_deals)))
            # display these deals as a table using pandas.DataFrame
            df=pd.DataFrame(list(position_deals),columns=position_deals[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        history_deals_get(from_date, to_date, group="*GBP*") = 14

        history_deals_get(from_date, to_date, group="*,!*EUR*,!*GBP*") = 7
        TradeDeal(ticket=506966741, order=0, time=1582202125, time_msc=1582202125419, type=2, entry=0, magic=0, position_id=0, reason=0, volume=0.0, pri ...
        TradeDeal(ticket=507962919, order=530218319, time=1582303777, time_msc=1582303777582, type=0, entry=0, magic=0, position_id=530218319, reason=0, ...
        TradeDeal(ticket=513149059, order=535548147, time=1583176242, time_msc=1583176242265, type=1, entry=1, magic=0, position_id=530218319, reason=0, ...
        TradeDeal(ticket=516943494, order=539349382, time=1583510003, time_msc=1583510003895, type=1, entry=0, magic=0, position_id=539349382, reason=0, ...
        TradeDeal(ticket=516943915, order=539349802, time=1583510025, time_msc=1583510025054, type=0, entry=0, magic=0, position_id=539349802, reason=0, ...
        TradeDeal(ticket=517139682, order=539557870, time=1583520201, time_msc=1583520201227, type=0, entry=1, magic=0, position_id=539349382, reason=0, ...
        TradeDeal(ticket=517139716, order=539557909, time=1583520202, time_msc=1583520202971, type=1, entry=1, magic=0, position_id=539349802, reason=0, ...

            ticket      order                time       time_msc  type  entry  magic  position_id  reason  volume    price  commission  swap     profit  fee  symbol comment external_id
        0  506966741          0 2020-02-20 12:35:25  1582202125419     2      0      0            0       0    0.00  0.00000         0.0   0.0  100000.00  0.0
        1  507962919  530218319 2020-02-21 16:49:37  1582303777582     0      0      0    530218319       0    0.01  0.97898         0.0   0.0       0.00  0.0  USDCHF
        2  513149059  535548147 2020-03-02 19:10:42  1583176242265     1      1      0    530218319       0    0.01  0.95758         0.0   0.0     -22.35  0.0  USDCHF
        3  516943494  539349382 2020-03-06 15:53:23  1583510003895     1      0      0    539349382       0    0.10  0.93475         0.0   0.0       0.00  0.0  USDCHF
        4  516943915  539349802 2020-03-06 15:53:45  1583510025054     0      0      0    539349802       0    0.10  0.66336         0.0   0.0       0.00  0.0  AUDUSD
        5  517139682  539557870 2020-03-06 18:43:21  1583520201227     0      1      0    539349382       0    0.10  0.93751         0.0   0.0     -29.44  0.0  USDCHF
        6  517139716  539557909 2020-03-06 18:43:22  1583520202971     1      1      0    539349802       0    0.10  0.66327         0.0   0.0      -0.90  0.0  AUDUSD

        Deals with position id #530218319: 2
            ticket      order                time       time_msc  type  entry  magic  position_id  reason  volume    price  commission  swap  profit  fee  symbol comment external_id
        0  507962919  530218319 2020-02-21 16:49:37  1582303777582     0      0      0    530218319       0    0.01  0.97898         0.0   0.0    0.00  0.0  USDCHF
        1  513149059  535548147 2020-03-02 19:10:42  1583176242265     1      1      0    530218319       0    0.01  0.95758         0.0   0.0  -22.35  0.0  USDCHF
        ```

        ## See also

            `history_deals_total`, `history_orders_get`
        :rtype: Any

        """
        code = f'mt5.history_deals_get(*{args},**{kwargs})'
        response = self.__conn.eval(code)
        return response
