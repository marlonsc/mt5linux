# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
# noqa: E501
"""
api_data.py - MetaTrader5 Data API for Neptor

Provides market data (bars and ticks) query methods compatible with the official MetaTrader5 Python API. Used for historical and real-time data queries in the Neptor platform.
"""


from typing import Any

from rpyc import classic


class MetaTrader5DataAPI:
    """Market data queries (bars and ticks) for MetaTrader5."""

    def __init__(self, host: str = 'localhost', port: int = 18812) -> None:
        """

        :param host:  (Default value = 'localhost')
        :type host: str
        :param port:  (Default value = 18812)
        :type port: int
        :rtype: None

        """
        self.__conn: Any = classic.connect(host, port)  # type: ignore
        self.__conn._config['sync_request_timeout'] = 300
        self.__conn.execute('import MetaTrader5 as mt5')

    def copy_rates_from(self, symbol: object, timeframe: object, date_from: object, count: object) -> Any:
        r"""# copy_rates_from

        Get bars from the MetaTrader 5 terminal starting from the specified date.

        ```python
        copy_rates_from(
           symbol,       # symbol name
           timeframe,    # timeframe
           date_from,    # initial bar open date
           count         # number of bars
           )
        ```

        ## Parameters

        - symbol

            [in]  Financial instrument name, for example, "EURUSD". Required unnamed parameter.

        - timeframe

            [in]  Timeframe the bars are requested for. Set by a value from the TIMEFRAME enumeration. Required unnamed parameter.

        - date_from

            [in]  Date of opening of the first bar from the requested sample. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - count

            [in]  Number of bars to receive. Required unnamed parameter.

        ## Return Value

        Returns bars as the numpy array with the named time, open, high, low, close, tick_volume, spread and real_volume columns. Return None in case of an error. The info on the error can be obtained using `last_error()`.

        ## Note

        See the `CopyRates()` function for more information.

        MetaTrader 5 terminal provides bars only within a history available to a user on charts. The number of bars available to users is set in the "Max. bars in chart" parameter.

        When creating the 'datetime' object, Python uses the local time zone, while MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time for executing functions that use time. Data received from the MetaTrader 5 terminal has UTC time.

        TIMEFRAME is an enumeration with possible chart period values

        | ID            | Description |
        |---------------|-------------|
        | TIMEFRAME_M1  | 1 minute    |
        | TIMEFRAME_M2  | 2 minutes   |
        | TIMEFRAME_M3  | 3 minutes   |
        | TIMEFRAME_M4  | 4 minutes   |
        | TIMEFRAME_M5  | 5 minutes   |
        | TIMEFRAME_M6  | 6 minutes   |
        | TIMEFRAME_M10 | 10 minutes  |
        | TIMEFRAME_M12 | 12 minutes  |
        | TIMEFRAME_M12 | 15 minutes  |
        | TIMEFRAME_M20 | 20 minutes  |
        | TIMEFRAME_M30 | 30 minutes  |
        | TIMEFRAME_H1  | 1 hour      |
        | TIMEFRAME_H2  | 2 hours     |
        | TIMEFRAME_H3  | 3 hours     |
        | TIMEFRAME_H4  | 4 hours     |
        | TIMEFRAME_H6  | 6 hours     |
        | TIMEFRAME_H8  | 8 hours     |
        | TIMEFRAME_H12 | 12 hours    |
        | TIMEFRAME_D1  | 1 day       |
        | TIMEFRAME_W1  | 1 week      |
        | TIMEFRAME_MN1 | 1 month     |


        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # import the 'pandas' module for displaying data obtained in the tabular form
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # import pytz module for working with time zone
        import pytz

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # set time zone to UTC
        timezone = pytz.timezone("Etc/UTC")
        # create 'datetime' object in UTC time zone to avoid the implementation of a local time zone offset
        utc_from = datetime(2020, 1, 10, tzinfo=timezone)
        # get 10 EURUSD H4 bars starting from 01.10.2020 in UTC time zone
        rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_H4, utc_from, 10)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        # display each element of obtained data in a new line
        print("Display obtained data 'as is'")
        for rate in rates:
            print(rate)

        # create DataFrame out of the obtained data
        rates_frame = pd.DataFrame(rates)
        # convert time in seconds into the datetime format
        rates_frame['time']=pd.to_datetime(rates_frame['time'], unit='s')

        # display data
        print("\nDisplay dataframe with data")
        print(rates_frame)
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Display obtained data 'as is'
        (1578484800, 1.11382, 1.11385, 1.1111, 1.11199, 9354, 1, 0)
        (1578499200, 1.11199, 1.11308, 1.11086, 1.11179, 10641, 1, 0)
        (1578513600, 1.11178, 1.11178, 1.11016, 1.11053, 4806, 1, 0)
        (1578528000, 1.11053, 1.11193, 1.11033, 1.11173, 3480, 1, 0)
        (1578542400, 1.11173, 1.11189, 1.11126, 1.11182, 2236, 1, 0)
        (1578556800, 1.11181, 1.11203, 1.10983, 1.10993, 7984, 1, 0)
        (1578571200, 1.10994, 1.11173, 1.10965, 1.11148, 7406, 1, 0)
        (1578585600, 1.11149, 1.11149, 1.10923, 1.11046, 7468, 1, 0)
        (1578600000, 1.11046, 1.11097, 1.11033, 1.11051, 3450, 1, 0)
        (1578614400, 1.11051, 1.11093, 1.11017, 1.11041, 2448, 1, 0)
        ```

        ## See also

            `CopyRates`, `copy_rates_from_pos`, `copy_rates_range`, `copy_ticks_from`, `copy_ticks_range`

        :param symbol: 
        :type symbol: object
        :param timeframe: 
        :type timeframe: object
        :param date_from: 
        :type date_from: object
        :param count: 
        :type count: object
        :rtype: Any

        """
        code = f'mt5.copy_rates_from({repr(symbol)}, {repr(timeframe)}, {repr(date_from)}, {repr(count)})'
        return classic.obtain(self.__conn.eval(code))  # type: ignore

    def copy_rates_from_pos(self, symbol: object, timeframe: object, start_pos: object, count: object) -> Any:
        r"""# copy_rates_from_pos

        Get bars from the MetaTrader 5 terminal starting from the specified index.

        ```python
        copy_rates_from_pos(
           symbol,       # symbol name
           timeframe,    # timeframe
           start_pos,    # initial bar index
           count         # number of bars
           )
        ```

        ## Parameters

        - symbol

            [in]  Financial instrument name, for example, "EURUSD". Required unnamed parameter.

        - timeframe

            [in]  Timeframe the bars are requested for. Set by a value from the TIMEFRAME enumeration. Required unnamed parameter.

        - start_pos

            [in]  Initial index of the bar the data are requested from. The numbering of bars goes from present to past. Thus, the zero bar means the current one. Required unnamed parameter.

        - count

            [in]  Number of bars to receive. Required unnamed parameter.

        ## Return Value

        Returns bars as the numpy array with the named time, open, high, low, close, tick_volume, spread and real_volume columns. Returns None in case of an error. The info on the error can be obtained using `last_error()`.

        ## Note

        See the `CopyRates()` function for more information.

        MetaTrader 5 terminal provides bars only within a history available to a user on charts. The number of bars available to users is set in the "Max. bars in chart" parameter.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # import the 'pandas' module for displaying data obtained in the tabular form
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # get 10 GBPUSD D1 bars from the current day
        rates = mt5.copy_rates_from_pos("GBPUSD", mt5.TIMEFRAME_D1, 0, 10)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        # display each element of obtained data in a new line
        print("Display obtained data 'as is'")
        for rate in rates:
            print(rate)

        # create DataFrame out of the obtained data
        rates_frame = pd.DataFrame(rates)
        # convert time in seconds into the datetime format
        rates_frame['time']=pd.to_datetime(rates_frame['time'], unit='s')

        # display data
        print("\nDisplay dataframe with data")
        print(rates_frame)
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Display obtained data 'as is'
        (1581552000, 1.29568, 1.30692, 1.29441, 1.30412, 68228, 0, 0)
        (1581638400, 1.30385, 1.30631, 1.3001, 1.30471, 56498, 0, 0)
        (1581897600, 1.30324, 1.30536, 1.29975, 1.30039, 49400, 0, 0)
        (1581984000, 1.30039, 1.30486, 1.29705, 1.29952, 62288, 0, 0)
        (1582070400, 1.29952, 1.3023, 1.29075, 1.29187, 57909, 0, 0)
        (1582156800, 1.29186, 1.29281, 1.28489, 1.28792, 61033, 0, 0)
        (1582243200, 1.28802, 1.29805, 1.28746, 1.29566, 66386, 0, 0)
        (1582502400, 1.29426, 1.29547, 1.28865, 1.29283, 66933, 0, 0)
        (1582588800, 1.2929, 1.30178, 1.29142, 1.30037, 80121, 0, 0)
        (1582675200, 1.30036, 1.30078, 1.29136, 1.29374, 49286, 0, 0)

        Display dataframe with data
                time     open     high      low    close  tick_volume  spread  real_volume
        0 2020-02-13  1.29568  1.30692  1.29441  1.30412        68228       0            0
        1 2020-02-14  1.30385  1.30631  1.30010  1.30471        56498       0            0
        2 2020-02-17  1.30324  1.30536  1.29975  1.30039        49400       0            0
        3 2020-02-18  1.30039  1.30486  1.29705  1.29952        62288       0            0
        4 2020-02-19  1.29952  1.30230  1.29075  1.29187        57909       0            0
        5 2020-02-20  1.29186  1.29281  1.28489  1.28792        61033       0            0
        6 2020-02-21  1.28802  1.29805  1.28746  1.29566        66386       0            0
        7 2020-02-24  1.29426  1.29547  1.28865  1.29283        66933       0            0
        8 2020-02-25  1.29290  1.30178  1.29142  1.30037        80121       0            0
        9 2020-02-26  1.30036  1.30078  1.29136  1.29374        49286       0            0
        ```

        ## See also

        `CopyRates`, `copy_rates_from`, `copy_rates_range`, `copy_ticks_from`, `copy_ticks_range`

        :param symbol: 
        :type symbol: object
        :param timeframe: 
        :type timeframe: object
        :param start_pos: 
        :type start_pos: object
        :param count: 
        :type count: object
        :rtype: Any

        """
        code = f'mt5.copy_rates_from_pos({repr(symbol)}, {repr(timeframe)}, {repr(start_pos)}, {repr(count)})'
        return classic.obtain(self.__conn.eval(code))  # type: ignore

    def copy_rates_range(self, symbol: object, timeframe: object, date_from: object, date_to: object) -> Any:
        r"""# copy_rates_range

        Get bars in the specified date range from the MetaTrader 5 terminal.

        ```python
        copy_rates_range(
           symbol,       # symbol name
           timeframe,    # timeframe
           date_from,    # date the bars are requested from
           date_to       # date, up to which the bars are requested
           )
        ```

        ## Parameters

        - symbol

            [in]  Financial instrument name, for example, "EURUSD". Required unnamed parameter.

        - timeframe

            [in]  Timeframe the bars are requested for. Set by a value from the TIMEFRAME enumeration. Required unnamed parameter.

        - date_from

            [in]  Date the bars are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Bars with the open time >= date_from are returned. Required unnamed parameter.

        - date_to

            [in]  Date, up to which the bars are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Bars with the open time <= date_to are returned. Required unnamed parameter.

        ## Return Value

        Returns bars as the numpy array with the named time, open, high, low, close, tick_volume, spread and real_volume columns. Returns None in case of an error. The info on the error can be obtained using `last_error()`.

        ## Note

        See the `CopyRates()` function for more information.

        MetaTrader 5 terminal provides bars only within a history available to a user on charts. The number of bars available to users is set in the "Max. bars in chart" parameter.

        When creating the 'datetime' object, Python uses the local time zone, while MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time for executing functions that use time. Data received from the MetaTrader 5 terminal has UTC time.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # import the 'pandas' module for displaying data obtained in the tabular form
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # import pytz module for working with time zone
        import pytz

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # set time zone to UTC
        timezone = pytz.timezone("Etc/UTC")
        # create 'datetime' objects in UTC time zone to avoid the implementation of a local time zone offset
        utc_from = datetime(2020, 1, 10, tzinfo=timezone)
        utc_to = datetime(2020, 1, 11, hour = 13, tzinfo=timezone)
        # get bars from USDJPY M5 within the interval of 2020.01.10 00:00 - 2020.01.11 13:00 in UTC time zone
        rates = mt5.copy_rates_range("USDJPY", mt5.TIMEFRAME_M5, utc_from, utc_to)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()

        # display each element of obtained data in a new line
        print("Display obtained data 'as is'")
        counter=0
        for rate in rates:
            counter+=1
            if counter<=10:
        print(rate)

        # create DataFrame out of the obtained data
        rates_frame = pd.DataFrame(rates)
        # convert time in seconds into the 'datetime' format
        rates_frame['time']=pd.to_datetime(rates_frame['time'], unit='s')

        # display data
        print("\nDisplay dataframe with data")
        print(rates_frame.head(10))
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Display obtained data 'as is'
        (1578614400, 109.513, 109.527, 109.505, 109.521, 43, 2, 0)
        (1578614700, 109.521, 109.549, 109.518, 109.543, 215, 8, 0)
        (1578615000, 109.543, 109.543, 109.466, 109.505, 98, 10, 0)
        (1578615300, 109.504, 109.534, 109.502, 109.517, 155, 8, 0)
        (1578615600, 109.517, 109.539, 109.513, 109.527, 71, 4, 0)
        (1578615900, 109.526, 109.537, 109.484, 109.52, 106, 9, 0)
        (1578616200, 109.52, 109.524, 109.508, 109.51, 205, 7, 0)
        (1578616500, 109.51, 109.51, 109.491, 109.496, 44, 8, 0)
        (1578616800, 109.496, 109.509, 109.487, 109.5, 85, 5, 0)
        (1578617100, 109.5, 109.504, 109.487, 109.489, 82, 7, 0)

        Display dataframe with data
                 time     open     high      low    close  tick_volume  spread  real_volume
        0 2020-01-10 00:00:00  109.513  109.527  109.505  109.521   43       2            0
        1 2020-01-10 00:05:00  109.521  109.549  109.518  109.543  215       8            0
        2 2020-01-10 00:10:00  109.543  109.543  109.466  109.505   98      10            0
        3 2020-01-10 00:15:00  109.504  109.534  109.502  109.517  155       8            0
        4 2020-01-10 00:20:00  109.517  109.539  109.513  109.527   71       4            0
        5 2020-01-10 00:25:00  109.526  109.537  109.484  109.520  106       9            0
        6 2020-01-10 00:30:00  109.520  109.524  109.508  109.510  205       7            0
        7 2020-01-10 00:35:00  109.510  109.510  109.491  109.496   44       8            0
        8 2020-01-10 00:40:00  109.496  109.509  109.487  109.500   85       5            0
        9 2020-01-10 00:45:00  109.500  109.504  109.487  109.489   82       7            0
        ```

        ## See also

            `CopyRates`, `copy_rates_from`, `copy_rates_range`, `copy_ticks_from`, `copy_ticks_range`

        :param symbol: 
        :type symbol: object
        :param timeframe: 
        :type timeframe: object
        :param date_from: 
        :type date_from: object
        :param date_to: 
        :type date_to: object
        :rtype: Any

        """
        code = f'mt5.copy_rates_range({repr(symbol)}, {repr(timeframe)}, {repr(date_from)}, {repr(date_to)})'
        return classic.obtain(self.__conn.eval(code))  # type: ignore

    def copy_ticks_from(self, symbol: object, date_from: object, count: object, flags: object) -> Any:
        r"""# copy_ticks_from

        Get ticks from the MetaTrader 5 terminal starting from the specified date.

        ```python
        copy_ticks_from(
           symbol,       # symbol name
           date_from,    # date the ticks are requested from
           count,# number of requested ticks
           flags # combination of flags defining the type of requested ticks
           )
        ```

        ## Parameters

        - symbol

            [in]  Financial instrument name, for example, "EURUSD". Required unnamed parameter.

        - from

            [in]  Date the ticks are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - count

            [in]  Number of ticks to receive. Required unnamed parameter.

        - flags

            [in]  A flag to define the type of the requested ticks. COPY_TICKS_INFO – ticks with Bid and/or Ask changes, COPY_TICKS_TRADE – ticks with changes in Last and Volume, COPY_TICKS_ALL – all ticks. Flag values are described in the COPY_TICKS enumeration. Required unnamed parameter.

        ## Return Value

        Returns ticks as the numpy array with the named time, bid, ask, last and flags columns. The 'flags' value can be a combination of flags from the TICK_FLAG enumeration. Return None in case of an error. The info on the error can be obtained using `last_error()`.

        ## Note

        See the CopyTicks function for more information.

        When creating the 'datetime' object, Python uses the local time zone, while MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time for executing functions that use time. Data received from the MetaTrader 5 terminal has UTC time.

        COPY_TICKS defines the types of ticks that can be requested using the `copy_ticks_from()` and `copy_ticks_range()` functions.

        | ID       | Description                                       |
        |------------------|---------------------------------------------------|
        | COPY_TICKS_ALL   | all ticks                                 |
        | COPY_TICKS_INFO  | ticks containing Bid and/or Ask price changes     |
        | COPY_TICKS_TRADE | ticks containing Last and/or Volume price changes |

        TICK_FLAG defines possible flags for ticks. These flags are used to describe ticks obtained by the `copy_ticks_from()` and `copy_ticks_range()` functions.

        | ID       | Description             |
        |------------------|-------------------------|
        | TICK_FLAG_BID    | Bid price changed       |
        | TICK_FLAG_ASK    | Ask price changed       |
        | TICK_FLAG_LAST   | Last price changed      |
        | TICK_FLAG_VOLUME | Volume changed  |
        | TICK_FLAG_BUY    | last Buy price changed  |
        | TICK_FLAG_SELL   | last Sell price changed |

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # import the 'pandas' module for displaying data obtained in the tabular form
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # import pytz module for working with time zone
        import pytz

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # set time zone to UTC
        timezone = pytz.timezone("Etc/UTC")
        # create 'datetime' object in UTC time zone to avoid the implementation of a local time zone offset
        utc_from = datetime(2020, 1, 10, tzinfo=timezone)
        # request 100 000 EURUSD ticks starting from 10.01.2019 in UTC time zone
        ticks = mt5.copy_ticks_from("EURUSD", utc_from, 100000, mt5.COPY_TICKS_ALL)
        print("Ticks received:",len(ticks))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()

        # display data on each tick on a new line
        print("Display obtained ticks 'as is'")
        count = 0
        for tick in ticks:
            count+=1
            print(tick)
            if count >= 10:
        break

        # create DataFrame out of the obtained data
        ticks_frame = pd.DataFrame(ticks)
        # convert time in seconds into the datetime format
        ticks_frame['time']=pd.to_datetime(ticks_frame['time'], unit='s')

        # display data
        print("\nDisplay dataframe with ticks")
        print(ticks_frame.head(10))
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Ticks received: 100000
        Display obtained ticks 'as is'
        (1578614400, 1.11051, 1.11069, 0., 0, 1578614400987, 134, 0.)
        (1578614402, 1.11049, 1.11067, 0., 0, 1578614402025, 134, 0.)
        (1578614404, 1.1105, 1.11066, 0., 0, 1578614404057, 134, 0.)
        (1578614404, 1.11049, 1.11067, 0., 0, 1578614404344, 134, 0.)
        (1578614412, 1.11052, 1.11064, 0., 0, 1578614412106, 134, 0.)
        (1578614418, 1.11039, 1.11051, 0., 0, 1578614418265, 134, 0.)
        (1578614418, 1.1104, 1.1105, 0., 0, 1578614418905, 134, 0.)
        (1578614419, 1.11039, 1.11051, 0., 0, 1578614419519, 134, 0.)
        (1578614456, 1.11037, 1.11065, 0., 0, 1578614456011, 134, 0.)
        (1578614456, 1.11039, 1.11051, 0., 0, 1578614456015, 134, 0.)

        Display dataframe with ticks
                 time      bid      ask  last  volume       time_msc  flags  volume_real
        0 2020-01-10 00:00:00  1.11051  1.11069   0.0       0  1578614400987    134  0.0
        1 2020-01-10 00:00:02  1.11049  1.11067   0.0       0  1578614402025    134  0.0
        2 2020-01-10 00:00:04  1.11050  1.11066   0.0       0  1578614404057    134  0.0
        3 2020-01-10 00:00:04  1.11049  1.11067   0.0       0  1578614404344    134  0.0
        4 2020-01-10 00:00:12  1.11052  1.11064   0.0       0  1578614412106    134  0.0
        5 2020-01-10 00:00:18  1.11039  1.11051   0.0       0  1578614418265    134  0.0
        6 2020-01-10 00:00:18  1.11040  1.11050   0.0       0  1578614418905    134  0.0
        7 2020-01-10 00:00:19  1.11039  1.11051   0.0       0  1578614419519    134  0.0
        8 2020-01-10 00:00:56  1.11037  1.11065   0.0       0  1578614456011    134  0.0
        9 2020-01-10 00:00:56  1.11039  1.11051   0.0       0  1578614456015    134  0.0
        ```

        ## See also

            `CopyRates`, `copy_rates_from_pos`, `copy_rates_range`, `copy_ticks_from`, `copy_ticks_range`

        :param symbol: 
        :type symbol: object
        :param date_from: 
        :type date_from: object
        :param count: 
        :type count: object
        :param flags: 
        :type flags: object
        :rtype: Any

        """
        code = f'mt5.copy_ticks_from({repr(symbol)}, {repr(date_from)}, {repr(count)}, {repr(flags)})'
        return classic.obtain(self.__conn.eval(code))  # type: ignore

    def copy_ticks_range(self, symbol: object, date_from: object, date_to: object, flags: object) -> Any:
        r"""# copy_ticks_range

        Get ticks for the specified date range from the MetaTrader 5 terminal.

        ```python
        copy_ticks_range(
           symbol,       # symbol name
           date_from,    # date the ticks are requested from
           date_to,      # date, up to which the ticks are requested
           flags # combination of flags defining the type of requested ticks
           )
        ```

        ## Parameters

        - symbol

            [in]  Financial instrument name, for example, "EURUSD". Required unnamed parameter.

        - date_from

            [in]  Date the ticks are requested from. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - date_to

            [in]  Date, up to which the ticks are requested. Set by the 'datetime' object or as a number of seconds elapsed since 1970.01.01. Required unnamed parameter.

        - flags

            [in]  A flag to define the type of the requested ticks. COPY_TICKS_INFO – ticks with Bid and/or Ask changes, COPY_TICKS_TRADE – ticks with changes in Last and Volume, COPY_TICKS_ALL – all ticks. Flag values are described in the COPY_TICKS enumeration. Required unnamed parameter.

        ## Return Value

        Returns ticks as the numpy array with the named time, bid, ask, last and flags columns. The 'flags' value can be a combination of flags from the TICK_FLAG enumeration. Return None in case of an error. The info on the error can be obtained using `last_error()`.

        ## Note

        See the CopyTicks function for more information.

        When creating the 'datetime' object, Python uses the local time zone, while MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time for executing functions that use time. The data obtained from MetaTrader 5 have UTC time, but Python applies the local time shift again when trying to print them. Thus, the obtained data should also be corrected for visual presentation.

        ## Example:

        ```python
        from datetime import datetime
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # import the 'pandas' module for displaying data obtained in the tabular form
        import pandas as pd
        pd.set_option('display.max_columns', 500) # number of columns to be displayed
        pd.set_option('display.width', 1500)      # max table width to display
        # import pytz module for working with time zone
        import pytz

        # establish connection to MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # set time zone to UTC
        timezone = pytz.timezone("Etc/UTC")
        # create 'datetime' objects in UTC time zone to avoid the implementation of a local time zone offset
        utc_from = datetime(2020, 1, 10, tzinfo=timezone)
        utc_to = datetime(2020, 1, 11, tzinfo=timezone)
        # request AUDUSD ticks within 11.01.2020 - 11.01.2020
        ticks = mt5.copy_ticks_range("AUDUSD", utc_from, utc_to, mt5.COPY_TICKS_ALL)
        print("Ticks received:",len(ticks))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()

        # display data on each tick on a new line
        print("Display obtained ticks 'as is'")
        count = 0
        for tick in ticks:
            count+=1
            print(tick)
            if count >= 10:
        break

        # create DataFrame out of the obtained data
        ticks_frame = pd.DataFrame(ticks)
        # convert time in seconds into the datetime format
        ticks_frame['time']=pd.to_datetime(ticks_frame['time'], unit='s')

        # display data
        print("\nDisplay dataframe with ticks")
        print(ticks_frame.head(10))
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29

        Ticks received: 37008
        Display obtained ticks 'as is'
        (1578614400, 0.68577, 0.68594, 0., 0, 1578614400820, 134, 0.)
        (1578614401, 0.68578, 0.68594, 0., 0, 1578614401128, 130, 0.)
        (1578614401, 0.68575, 0.68594, 0., 0, 1578614401128, 130, 0.)
        (1578614411, 0.68576, 0.68594, 0., 0, 1578614411388, 130, 0.)
        (1578614411, 0.68575, 0.68594, 0., 0, 1578614411560, 130, 0.)
        (1578614414, 0.68576, 0.68595, 0., 0, 1578614414973, 134, 0.)
        (1578614430, 0.68576, 0.68594, 0., 0, 1578614430188, 4, 0.)
        (1578614450, 0.68576, 0.68595, 0., 0, 1578614450408, 4, 0.)
        (1578614450, 0.68576, 0.68594, 0., 0, 1578614450519, 4, 0.)
        (1578614456, 0.68575, 0.68594, 0., 0, 1578614456363, 130, 0.)

        Display dataframe with ticks
                 time      bid      ask  last  volume       time_msc  flags  volume_real
        0 2020-01-10 00:00:00  0.68577  0.68594   0.0       0  1578614400820    134  0.0
        1 2020-01-10 00:00:01  0.68578  0.68594   0.0       0  1578614401128    130  0.0
        2 2020-01-10 00:00:01  0.68575  0.68594   0.0       0  1578614401128    130  0.0
        3 2020-01-10 00:00:11  0.68576  0.68594   0.0       0  1578614411388    130  0.0
        4 2020-01-10 00:00:11  0.68575  0.68594   0.0       0  1578614411560    130  0.0
        5 2020-01-10 00:00:14  0.68576  0.68595   0.0       0  1578614414973    134  0.0
        6 2020-01-10 00:00:30  0.68576  0.68594   0.0       0  1578614430188      4  0.0
        7 2020-01-10 00:00:50  0.68576  0.68595   0.0       0  1578614450408      4  0.0
        8 2020-01-10 00:00:50  0.68576  0.68594   0.0       0  1578614450519      4  0.0
        9 2020-01-10 00:00:56  0.68575  0.68594   0.0       0  1578614456363    130  0.0
        ```

        ## See also

            `CopyRates`, `copy_rates_from_pos`, `copy_rates_range`, `copy_ticks_from`, `copy_ticks_range`

        :param symbol: 
        :type symbol: object
        :param date_from: 
        :type date_from: object
        :param date_to: 
        :type date_to: object
        :param flags: 
        :type flags: object
        :rtype: Any

        """
        code = f'mt5.copy_ticks_range({repr(symbol)}, {repr(date_from)}, {repr(date_to)}, {repr(flags)})'
        return classic.obtain(self.__conn.eval(code))  # type: ignore
