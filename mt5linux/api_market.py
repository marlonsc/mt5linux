# pylint: disable=line-too-long, fixme
"""
api_market.py - MetaTrader5 Market API bridge for Neptor

Provides Pythonic access to MetaTrader5 market and symbol queries via RPyC. Used for symbol, tick, and market depth operations in the Neptor platform. All methods are mockups or wrappers for remote MT5 API calls.
"""
# =====================================================================================
# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# noqa: E501

from typing import Any

import rpyc


class MetaTrader5MarketAPI:
    """Market and symbol queries for MetaTrader5."""

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

    def symbols_total(self, *args: object, **kwargs: object) -> Any:
        r"""# symbols_total

        Get the number of all financial instruments in the MetaTrader 5 terminal.

        ```python
        symbols_total()
        ```

        ## Return Value

        Integer value.

        ## Note

        The function is similar to `SymbolsTotal()`. However, it returns the number of all symbols including custom ones and the ones disabled in MarketWatch.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get the number of financial instruments
        symbols=mt5.symbols_total()
        if symbols>0:
            print("Total symbols =",symbols)
        else:
            print("symbols not found")

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `symbols_get`, `symbol_select`, `symbol_info`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.symbols_total(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def symbols_get(self, *args: object, **kwargs: object) -> Any:
        r"""# symbols_get

        Get all financial instruments from the MetaTrader 5 terminal.

        ```python
        symbols_get(
            group="GROUP"      # symbol selection filter
        )
        ```

        - group="GROUP"

            [in]  The filter for arranging a group of necessary symbols. Optional parameter. If the group is specified, the function returns only symbols meeting a specified criteria.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The group parameter allows sorting out symbols by name. '*' can be used at the beginning and the end of a string.

        The group parameter can be used as a named or an unnamed one. Both options work the same way. The named option (group="GROUP") makes the code easier to read.

        The group parameter may contain several comma separated conditions. A condition can be set as a mask using '*'. The logical negation symbol '!' can be used for an exclusion. All conditions are applied sequentially, which means conditions of including to a group should be specified first followed by an exclusion condition. For example, group="*, !EUR" means that all symbols should be selected first and the ones containing "EUR" in their names should be excluded afterwards.

        Unlike `symbol_info()`, the `symbols_get()` function returns data on all requested symbols within a single call.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get all symbols
        symbols=mt5.symbols_get()
        print('Symbols: ', len(symbols))
        count=0
        # display the first five ones
        for s in symbols:
            count+=1
            print("{}. {}".format(count,s.name))
            if count==5: break
        print()

        # get symbols containing RU in their names
        ru_symbols=mt5.symbols_get("*RU*")
        print('len(*RU*): ', len(ru_symbols))
        for s in ru_symbols:
            print(s.name)
        print()

        # get symbols whose names do not contain USD, EUR, JPY and GBP
        group_symbols=mt5.symbols_get(group="*,!*USD*,!*EUR*,!*JPY*,!*GBP*")
        print('len(*,!*USD*,!*EUR*,!*JPY*,!*GBP*):', len(group_symbols))
        for s in group_symbols:
            print(s.name,":",s)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        Symbols:  84
        1. EURUSD
        2. GBPUSD
        3. USDCHF
        4. USDJPY
        5. USDCNH

        len(*RU*):  8
        EURUSD
        USDRUB
        USDRUR
        EURRUR
        EURRUB
        FORTS.RUB.M5
        EURUSD_T20
        EURUSD4

        len(*,!*USD*,!*EUR*,!*JPY*,!*GBP*):  13
        AUDCAD : SymbolInfo(custom=False, chart_mode=0, select=True, visible=True, session_deals=0, session_buy_orders=0, session...
        AUDCHF : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        AUDNZD : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        CADCHF : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        NZDCAD : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        NZDCHF : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        NZDSGD : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        CADMXN : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        CHFMXN : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        NZDMXN : SymbolInfo(custom=False, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, sessi...
        FORTS.RTS.M5 : SymbolInfo(custom=True, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, ...
        FORTS.RUB.M5 : SymbolInfo(custom=True, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, ...
        FOREX.CHF.M5 : SymbolInfo(custom=True, chart_mode=0, select=False, visible=False, session_deals=0, session_buy_orders=0, ...
        ```

        ## See also

            `symbols_total`, `symbol_select`, `symbol_info`
        :rtype: Any

        """
        code = f'mt5.symbols_get(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def symbol_info_tick(self, *args: object, **kwargs: object) -> Any:
        r"""# symbol_info_tick

        Get the last tick for the specified financial instrument.

        ```python
        symbol_info_tick(
            symbol      # financial instrument name
        )
        ```

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function is similar to SymbolInfoTick.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # attempt to enable the display of the GBPUSD in MarketWatch
        selected=mt5.symbol_select("GBPUSD",True)
        if not selected:
            print("Failed to select GBPUSD")
            mt5.shutdown()
            quit()

        # display the last GBPUSD tick
        lasttick=mt5.symbol_info_tick("GBPUSD")
        print(lasttick)
        # display tick field values in the form of a list
        print("Show symbol_info_tick(\"GBPUSD\")._asdict():")
        symbol_info_tick_dict = mt5.symbol_info_tick("GBPUSD")._asdict()
        for prop in symbol_info_tick_dict:
            print("  {}={}".format(prop, symbol_info_tick_dict[prop]))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        Tick(time=1585070338, bid=1.17264, ask=1.17279, last=0.0, volume=0, time_msc=1585070338728, flags=2, volume_real=0.0)
        Show symbol_info_tick._asdict():
            time=1585070338
            bid=1.17264
            ask=1.17279
            last=0.0
            volume=0
            time_msc=1585070338728
            flags=2
            volume_real=0.0
        ```

        ## See also

            ``symbol_info`
        :rtype: Any

        """
        code = f'mt5.symbol_info_tick(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def symbol_select(self, *args: object, **kwargs: object) -> Any:
        r"""# symbol_select

        Select a symbol in the MarketWatch window or remove a symbol from the window.

        ```python
        symbol_select(
            symbol,      # financial instrument name
            enable       # enable or disable
        )
        ```

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        - enable

            [in]  Switch. Optional unnamed parameter. If 'false', a symbol should be removed from the MarketWatch window. Otherwise, it should be selected in the MarketWatch window. A symbol cannot be removed if open charts with this symbol are currently present or positions are opened on it.

        ## Return Value

        `True` if successful, otherwise – `False`.

        ## Note

        The function is similar to `SymbolSelect`.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print()
        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize(login=25115284, server="MetaQuotes-Demo",password="4zatlbqx"):
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # attempt to enable the display of the EURCAD in MarketWatch
        selected=mt5.symbol_select("EURCAD",True)
        if not selected:
            print("Failed to select EURCAD, error code =",mt5.last_error())
        else:
            symbol_info=mt5.symbol_info("EURCAD")
            print(symbol_info)
            print("EURCAD: currency_base =",symbol_info.currency_base,"  currency_profit =",symbol_info.currency_profit,"  currency_margin =",symbol_info.currency_margin)
            print()

            # get symbol properties in the form of a dictionary
            print("Show symbol_info()._asdict():")
            symbol_info_dict = symbol_info._asdict()
            for prop in symbol_info_dict:
                print("  {}={}".format(prop, symbol_info_dict[prop]))
            print()

            # convert the dictionary into DataFrame and print
            df=pd.DataFrame(list(symbol_info_dict.items()),columns=['property','value'])
            print("symbol_info_dict() as dataframe:")
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        SymbolInfo(custom=False, chart_mode=0, select=True, visible=True, session_deals=0, session_buy_orders=0, session_sell_orders=0, volume=0, volumehigh=0, ....
        EURCAD: currency_base = EUR   currency_profit = CAD   currency_margin = EUR

        Show symbol_info()._asdict():
            custom=False
            chart_mode=0
            select=True
            visible=True
            session_deals=0
            session_buy_orders=0
            session_sell_orders=0
            volume=0
            volumehigh=0
            volumelow=0
            time=1585217595
            digits=5
            spread=39
            spread_float=True
            ticks_bookdepth=10
            trade_calc_mode=0
            trade_mode=4
            start_time=0
            expiration_time=0
            trade_stops_level=0
            trade_freeze_level=0
            trade_exemode=1
            swap_mode=1
            swap_rollover3days=3
            margin_hedged_use_leg=False
            expiration_mode=7
            filling_mode=1
            order_mode=127
            order_gtc_mode=0
            option_mode=0
            option_right=0
            bid=1.55192
            bidhigh=1.55842
            bidlow=1.5419800000000001
            ask=1.5523099999999999
            askhigh=1.55915
            asklow=1.5436299999999998
            last=0.0
            lasthigh=0.0
            lastlow=0.0
            volume_real=0.0
            volumehigh_real=0.0
            volumelow_real=0.0
            option_strike=0.0
            point=1e-05
            trade_tick_value=0.7043642408362214
            trade_tick_value_profit=0.7043642408362214
            trade_tick_value_loss=0.7044535553770941
            trade_tick_size=1e-05
            trade_contract_size=100000.0
            trade_accrued_interest=0.0
            trade_face_value=0.0
            trade_liquidity_rate=0.0
            volume_min=0.01
            volume_max=500.0
            volume_step=0.01
            volume_limit=0.0
            swap_long=-1.1
            swap_short=-0.9
            margin_initial=0.0
            margin_maintenance=0.0
            session_volume=0.0
            session_turnover=0.0
            session_interest=0.0
            session_buy_orders_volume=0.0
            session_sell_orders_volume=0.0
            session_open=0.0
            session_close=0.0
            session_aw=0.0
            session_price_settlement=0.0
            session_price_limit_min=0.0
            session_price_limit_max=0.0
            margin_hedged=100000.0
            price_change=0.0
            price_volatility=0.0
            price_theoretical=0.0
            price_greeks_delta=0.0
            price_greeks_theta=0.0
            price_greeks_gamma=0.0
            price_greeks_vega=0.0
            price_greeks_rho=0.0
            price_greeks_omega=0.0
            price_sensitivity=0.0
            basis=
            category=
            currency_base=EUR
            currency_profit=CAD
            currency_margin=EUR
            bank=
            description=Euro vs Canadian Dollar
            exchange=
            formula=
            isin=
            name=EURCAD
            page=http://www.google.com/finance?q=EURCAD
            path=Forex\EURCAD

        symbol_info_dict() as dataframe:
                 property                                   value
        0          custom                                   False
        1      chart_mode                                       0
        2          select                                    True
        3         visible                                    True
        4   session_deals                                       0
        ..            ...                                     ...
        91        formula
        92           isin
        93           name                                  EURCAD
        94           page  http://www.google.com/finance?q=EURCAD
        95           path                            Forex\EURCAD

        [96 rows x 2 columns]
        ```

        ## See also

            `symbol_info`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.symbol_select(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def market_book_add(self, *args: object, **kwargs: object) -> Any:
        r"""# market_book_add

        Subscribes the MetaTrader 5 terminal to the Market Depth change events for a specified symbol.

        ```python
        market_book_add(
            symbol      # financial instrument name
        )
        ```

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        ## Return Value

        `True` if successful, otherwise – `False`.

        ## Note

        The function is similar to `MarketBookAdd`.

        ## See also

            `market_book_get`, `market_book_release`, Market Depth structure

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.market_book_add(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def market_book_get(self, *args: object, **kwargs: object) -> Any:
        r"""# market_book_get

        Returns a tuple from `BookInfo` featuring Market Depth entries for the specified symbol.

        ```python
        market_book_get(
           symbol      # financial instrument name
        )
        ```

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        ## Return Value

        Returns the Market Depth content as a tuple from `BookInfo` entries featuring order type, price and volume in lots. `BookInfo` is similar to the `MqlBookInfo` structure.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The subscription to the Market Depth change events should be preliminarily performed using the `market_book_add()` function.

        The function is similar to `MarketBookGet`.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import time
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        print("")

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
           # shut down connection to the MetaTrader 5 terminal
            mt5.shutdown()
            quit()

        # subscribe to market depth updates for EURUSD (Depth of Market)
        if mt5.market_book_add('EURUSD'):
            # get the market depth data 10 times in a loop
            for i in range(10):
                    # get the market depth content (Depth of Market)
                    items = mt5.market_book_get('EURUSD')
                    # display the entire market depth 'as is' in a single string
                    print(items)
                    # now display each order separately for more clarity
                    if items:
                        for it in items:
                            # order content
                            print(it._asdict())
                    # pause for 5 seconds before the next request of the market depth data
                    time.sleep(5)
            # cancel the subscription to the market depth updates (Depth of Market)
            mt5.market_book_release('EURUSD')
        else:
            print("mt5.market_book_add('EURUSD') failed, error code =",mt5.last_error())

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.34

        (BookInfo(type=1, price=1.20038, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20032, volume=100, volume...
        {'type': 1, 'price': 1.20038, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20032, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.2003, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20028, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20026, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20025, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20023, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20017, 'volume': 250, 'volume_dbl': 250.0}
        (BookInfo(type=1, price=1.2004299999999999, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20037, volume...
        {'type': 1, 'price': 1.2004299999999999, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20037, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.20036, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20034, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20031, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20029, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20028, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20022, 'volume': 250, 'volume_dbl': 250.0}
        (BookInfo(type=1, price=1.2004299999999999, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20037, volume...
        {'type': 1, 'price': 1.2004299999999999, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20037, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.20036, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20034, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20031, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20029, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20028, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20022, 'volume': 250, 'volume_dbl': 250.0}
        (BookInfo(type=1, price=1.20036, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20029, volume=100, volume...
        {'type': 1, 'price': 1.20036, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20029, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.20028, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20026, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20023, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20022, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20021, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20014, 'volume': 250, 'volume_dbl': 250.0}
        (BookInfo(type=1, price=1.20035, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20029, volume=100, volume...
        {'type': 1, 'price': 1.20035, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20029, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.20027, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20025, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20023, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20022, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20021, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20014, 'volume': 250, 'volume_dbl': 250.0}
        (BookInfo(type=1, price=1.20037, volume=250, volume_dbl=250.0), BookInfo(type=1, price=1.20031, volume=100, volume...
        {'type': 1, 'price': 1.20037, 'volume': 250, 'volume_dbl': 250.0}
        {'type': 1, 'price': 1.20031, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 1, 'price': 1.2003, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 1, 'price': 1.20028, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20025, 'volume': 36, 'volume_dbl': 36.0}
        {'type': 2, 'price': 1.20023, 'volume': 50, 'volume_dbl': 50.0}
        {'type': 2, 'price': 1.20022, 'volume': 100, 'volume_dbl': 100.0}
        {'type': 2, 'price': 1.20016, 'volume': 250, 'volume_dbl': 250.0}
        ```

        ## See also

            `market_book_add`, `market_book_release`, Market Depth structure
        :rtype: Any

        """
        code = f'mt5.market_book_get(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def market_book_release(self, symbol: object) -> Any:
        r"""# market_book_release

        Cancels subscription of the MetaTrader 5 terminal to the Market Depth change events for a specified symbol.

        ```python
        market_book_release(
            symbol      # financial instrument name
        )
        ```

        - symbol

            [in]  Financial instrument name. Required unnamed parameter.

        ## Return Value

        `True` if successful, otherwise – `False`.

        ## Note

        The function is similar to `MarketBookRelease`.

        ## See also

            `market_book_add`, `market_book_get`, Market Depth structure

        :param symbol: 
        :type symbol: object
        :rtype: Any

        """
        code = f'mt5.market_book_release({repr(symbol)})'
        return self.__conn.eval(code)
