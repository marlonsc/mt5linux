"""
api_account.py - MetaTrader5 Account API for Neptor

Provides a MetaTrader5 Python API compatible interface for account management, login, and terminal operations. Used for account, session, and terminal control in the Neptor platform.
"""

# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
# noqa: E501

from typing import Any

import rpyc


class MetaTrader5:
    """MetaTrader5 Python API compatible interface."""

    def __init__(self, host: str = 'localhost', port: int = 18812) -> None:
        """host: str
            default = localhost
        port: int
            default = 18812

        :param host:  (Default value = 'localhost')
        :type host: str
        :param port:  (Default value = 18812)
        :type port: int
        :rtype: None

        """
        self.__conn: Any = rpyc.classic.connect(host, port)  # type: ignore
        self.__conn._config['sync_request_timeout'] = 300  # 5 min
        self.__conn.execute('import MetaTrader5 as mt5')
        self.__conn.execute('import datetime')

    def __del__(self) -> None:
        """


        :rtype: None

        """

    def initialize(self, *args: object, **kwargs: object) -> Any:
        r"""# initialize

        Establish a connection with the MetaTrader 5 terminal. There are three call options.

        Call without parameters. The terminal for connection is found automatically.

        ```python
        initialize()
        ```

        Call specifying the path to the MetaTrader 5 terminal we want to connect to.

        ```python
        initialize(
           path                      # path to the MetaTrader 5 terminal EXE file
           )
        ```

        Call specifying the trading account path and parameters.

        ```python
        initialize(
           path,                     # path to the MetaTrader 5 terminal EXE file
           login=LOGIN,              # account number
           password="PASSWORD",      # password
           server="SERVER",          # server name as it is specified in the terminal
           timeout=TIMEOUT,          # timeout
           portable=False            # portable mode
           )
        ```

        ## Parameters

        - path

            [in]  Path to the metatrader.exe or metatrader64.exe file. Optional unnamed parameter. It is indicated first without a parameter name. If the path is not specified, the module attempts to find the executable file on its own.

        - login=LOGIN

            [in]  Trading account number. Optional named parameter. If not specified, the last trading account is used.

        - password="PASSWORD"

            [in]  Trading account password. Optional named parameter. If the password is not set, the password for a specified trading account saved in the terminal database is applied automatically.

        - server="SERVER"

            [in]  Trade server name. Optional named parameter. If the server is not set, the server for a specified trading account saved in the terminal database is applied automatically.

        - timeout=TIMEOUT

            [in]  Connection timeout in milliseconds. Optional named parameter. If not specified, the value of 60 000 (60 seconds) is applied.

        - portable=False

            [in]  Flag of the terminal launch in portable mode. Optional named parameter. If not specified, the value of False is used.

        ## Return Value

            Returns True in case of successful connection to the MetaTrader 5 terminal, otherwise - False.

        ## Note

            If required, the MetaTrader 5 terminal is launched to establish connection when executing the initialize() call.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish MetaTrader 5 connection to a specified trading account
        if not mt5.initialize(login=25115284, server="MetaQuotes-Demo",password="4zatlbqx"):
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # display data on connection status, server name and trading account
        print(mt5.terminal_info())
        # display data on MetaTrader 5 version
        print(mt5.version())

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `shutdown`, `terminal_info`, `version`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.initialize(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def login(self, *args: object, **kwargs: object) -> Any:
        r"""# login

        Connect to a trading account using specified parameters.

        ```python
        login(
           login,                    # account number
           password="PASSWORD",      # password
           server="SERVER",          # server name as it is specified in the terminal
           timeout=TIMEOUT           # timeout
           )
        ```

        ## Parameters

        - login

            [in]  Trading account number. Required unnamed parameter.

        - password

            [in]  Trading account password. Optional named parameter. If the password is not set, the password saved in the terminal database is applied automatically.

        - server

            [in]  Trade server name. Optional named parameter. If no server is set, the last used server is applied automatically.

        - timeout=TIMEOUT

            [in]  Connection timeout in milliseconds. Optional named parameter. If not specified, the value of 60 000 (60 seconds) is applied. If the connection is not established within the specified time, the call is forcibly terminated and the exception is generated.

        ## Return Value

        True in case of a successful connection to the trade account, otherwise – False.

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

        # display data on MetaTrader 5 version
        print(mt5.version())
        # connect to the trade account without specifying a password and a server
        account=17221085
        authorized=mt5.login(account)  # the terminal database password is applied if connection data is set to be remembered
        if authorized:
            print("connected to account #{}".format(account))
        else:
            print("failed to connect at account #{}, error code: {}".format(account, mt5.last_error()))

        # now connect to another trading account specifying the password
        account=25115284
        authorized=mt5.login(account, password="gqrtz0lbdm")
        if authorized:
            # display trading account data 'as is'
            print(mt5.account_info())
            # display trading account data in the form of a list
            print("Show account_info()._asdict():")
            account_info_dict = mt5.account_info()._asdict()
            for prop in account_info_dict:
                print("  {}={}".format(prop, account_info_dict[prop]))
        else:
            print("failed to connect at account #{}, error code: {}".format(account, mt5.last_error()))

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        [500, 2367, '23 Mar 2020']

        connected to account #17221085

        connected to account #25115284
        AccountInfo(login=25115284, trade_mode=0, leverage=100, limit_orders=200, margin_so_mode=0, ...
        account properties:
           login=25115284
           trade_mode=0
           leverage=100
           limit_orders=200
           margin_so_mode=0
           trade_allowed=True
           trade_expert=True
           margin_mode=2
           currency_digits=2
           fifo_close=False
           balance=99588.33
           credit=0.0
           profit=-45.23
           equity=99543.1
           margin=54.37
           margin_free=99488.73
           margin_level=183084.6054809638
           margin_so_call=50.0
           margin_so_so=30.0
           margin_initial=0.0
           margin_maintenance=0.0
           assets=0.0
           liabilities=0.0
           commission_blocked=0.0
           name=James Smith
           server=MetaQuotes-Demo
           currency=USD
           company=MetaQuotes Software Corp.
        ```

        ## See also

            `initialize`, `shutdown`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.login(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def shutdown(self, *args: object, **kwargs: object) -> Any:
        r"""# shutdown

        Close the previously established connection to the MetaTrader 5 terminal.

        ```python
        shutdown()
        ```

        ## Return Value

        None.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed")
            quit()

        # display data on connection status, server name and trading account
        print(mt5.terminal_info())
        # display data on MetaTrader 5 version
        print(mt5.version())

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `initialize`, `login_py`, `terminal_info`, `version`

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        code = f'mt5.shutdown(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def last_error(self, *args: object, **kwargs: object) -> Any:
        r"""# last_error

        Return data on the last error.

        ```python
        last_error()
        ```

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        `last_error()` allows obtaining an error code in case of a failed execution of a MetaTrader 5 library function. It is similar to `GetLastError()`. However, it applies its own error codes. Possible values:

        | Constant                    | Value  | Description                      |
        |-----------------------------|--------|----------------------------------|
        | RES_S_OK                    | 1      | generic success                  |
        | RES_E_FAIL                  | -1     | generic fail                     |
        | RES_E_INVALID_PARAMS        | -2     | invalid arguments/parameters     |
        | RES_E_NO_MEMORY             | -3     | no memory condition              |
        | RES_E_NOT_FOUND             | -4     | no history                       |
        | RES_E_INVALID_VERSION       | -5     | invalid version                  |
        | RES_E_AUTH_FAILED           | -6     | authorization failed             |
        | RES_E_UNSUPPORTED           | -7     | unsupported method               |
        | RES_E_AUTO_TRADING_DISABLED | -8     | auto-trading disabled            |
        | RES_E_INTERNAL_FAIL         | -10000 | internal IPC general error       |
        | RES_E_INTERNAL_FAIL_SEND    | -10001 | internal IPC send failed         |
        | RES_E_INTERNAL_FAIL_RECEIVE | -10002 | internal IPC recv failed         |
        | RES_E_INTERNAL_FAIL_INIT    | -10003 | internal IPC initialization fail |
        | RES_E_INTERNAL_FAIL_CONNECT | -10003 | internal IPC no ipc              |
        | RES_E_INTERNAL_FAIL_TIMEOUT | -10005 | internal timeout                 |

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

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## See also

            `version`, `GetLastError`
        :rtype: Any

        """
        code = f'mt5.last_error(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def account_info(self, *args: object, **kwargs: object) -> Any:
        r"""# account_info

        Get info on the current trading account.

        ```python
        account_info()
        ```

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function returns all data that can be obtained using `AccountInfoInteger`, `AccountInfoDouble` and `AccountInfoString` in one call.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # connect to the trade account specifying a password and a server
        authorized=mt5.login(25115284, password="gqz0343lbdm")
        if authorized:
            account_info=mt5.account_info()
            if account_info!=None:
                # display trading account data 'as is'
                print(account_info)
                # display trading account data in the form of a dictionary
                print("Show account_info()._asdict():")
                account_info_dict = mt5.account_info()._asdict()
                for prop in account_info_dict:
                    print("  {}={}".format(prop, account_info_dict[prop]))
                print()

                # convert the dictionary into DataFrame and print
                df=pd.DataFrame(list(account_info_dict.items()),columns=['property','value'])
                print("account_info() as dataframe:")
                print(df)
        else:
            print("failed to connect to trade account 25115284 with password=gqz0343lbdm, error code =",mt5.last_error())

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        AccountInfo(login=25115284, trade_mode=0, leverage=100, limit_orders=200, margin_so_mode=0, ....
        Show account_info()._asdict():
          login=25115284
          trade_mode=0
          leverage=100
          limit_orders=200
          margin_so_mode=0
          trade_allowed=True
          trade_expert=True
          margin_mode=2
          currency_digits=2
          fifo_close=False
          balance=99511.4
          credit=0.0
          profit=41.82
          equity=99553.22
          margin=98.18
          margin_free=99455.04
          margin_level=101398.67590140559
          margin_so_call=50.0
          margin_so_so=30.0
          margin_initial=0.0
          margin_maintenance=0.0
          assets=0.0
          liabilities=0.0
          commission_blocked=0.0
          name=MetaQuotes Dev Demo
          server=MetaQuotes-Demo
          currency=USD
          company=MetaQuotes Software Corp.

        account_info() as dataframe:
                      property                      value
        0                login                   25115284
        1           trade_mode                          0
        2             leverage                        100
        3         limit_orders                        200
        4       margin_so_mode                          0
        5        trade_allowed                       True
        6         trade_expert                       True
        7          margin_mode                          2
        8      currency_digits                          2
        9           fifo_close                      False
        10             balance                    99588.3
        11              credit                          0
        12              profit                     -45.13
        13              equity                    99543.2
        14              margin                      54.37
        15         margin_free                    99488.8
        16        margin_level                     183085
        17      margin_so_call                         50
        18        margin_so_so                         30
        19      margin_initial                          0
        20  margin_maintenance                          0
        21              assets                          0
        22         liabilities                          0
        23  commission_blocked                          0
        24                name                James Smith
        25              server            MetaQuotes-Demo
        26            currency                        USD
        27             company  MetaQuotes Software Corp.
        ```

        ## See also

            `initialize`, `shutdown`, `login`
        :rtype: Any

        """
        code = f'mt5.account_info(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def terminal_info(self, *args: object, **kwargs: object) -> Any:
        r"""# terminal_info

        Get the connected MetaTrader 5 client terminal status and settings.

        ```python
        terminal_info()
        ```

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The function returns all data that can be obtained using `TerminalInfoInteger`, `TerminalInfoDouble` and `TerminalInfoDouble` in one call.

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # display data on MetaTrader 5 version
        print(mt5.version())
        # display info on the terminal settings and status
        terminal_info=mt5.terminal_info()
        if terminal_info!=None:
            # display the terminal data 'as is'
            print(terminal_info)
            # display data in the form of a list
            print("Show terminal_info()._asdict():")
            terminal_info_dict = mt5.terminal_info()._asdict()
            for prop in terminal_info_dict:
                print("  {}={}".format(prop, terminal_info_dict[prop]))
            print()
            # convert the dictionary into DataFrame and print
            df=pd.DataFrame(list(terminal_info_dict.items()),columns=['property','value'])
            print("terminal_info() as dataframe:")
            print(df)

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:

        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        [500, 2366, '20 Mar 2020']
        TerminalInfo(community_account=True, community_connection=True, connected=True,....
        Show terminal_info()._asdict():
          community_account=True
          community_connection=True
          connected=True
          dlls_allowed=False
          trade_allowed=False
          tradeapi_disabled=False
          email_enabled=False
          ftp_enabled=False
          notifications_enabled=False
          mqid=False
          build=2366
          maxbars=5000
          codepage=1251
          ping_last=77850
          community_balance=707.10668201585
          retransmission=0.0
          company=MetaQuotes Software Corp.
          name=MetaTrader 5
          language=Russian
          path=E:\ProgramFiles\MetaTrader 5
          data_path=E:\ProgramFiles\MetaTrader 5
          commondata_path=C:\Users\Rosh\AppData\Roaming\MetaQuotes\Terminal\Common

        terminal_info() as dataframe:
                         property                      value
        0       community_account                       True
        1    community_connection                       True
        2               connected                       True
        3            dlls_allowed                      False
        4           trade_allowed                      False
        5       tradeapi_disabled                      False
        6           email_enabled                      False
        7             ftp_enabled                      False
        8   notifications_enabled                      False
        9                    mqid                      False
        10                  build                       2367
        11                maxbars                       5000
        12               codepage                       1251
        13              ping_last                      80953
        14      community_balance                    707.107
        15         retransmission                   0.063593
        16                company  MetaQuotes Software Corp.
        17                   name               MetaTrader 5
        18               language                    Russian
        ```

        ## See also

            `initialize`, `shutdown`, `version`
        :rtype: Any

        """
        code = f'mt5.terminal_info(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def version(self, *args: object, **kwargs: object) -> Any:
        r"""# version

        Return the MetaTrader 5 terminal version.

        ```python
        version()
        ```

        ## Return Value

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: ## Note

        The `version()` function returns the terminal version, build and release date as a tuple of three values:

        | Type    | Description                   | Sample value  |
        |---------|-------------------------------|---------------|
        | integer | MetaTrader 5 terminal version | 500           |
        | integer | Build                         | 2007          |
        | string  | Build release date            | '25 Feb 2019' |

        ## Example:

        ```python
        import MetaTrader5 as mt5
        import pandas as pd
        # display data on the MetaTrader 5 package
        print("MetaTrader5 package author: ",mt5.__author__)
        print("MetaTrader5 package version: ",mt5.__version__)

        # establish connection to the MetaTrader 5 terminal
        if not mt5.initialize():
            print("initialize() failed, error code =",mt5.last_error())
            quit()

        # display data on MetaTrader 5 version
        print(mt5.version())

        # display data on connection status, server name and trading account 'as is'
        print(mt5.terminal_info())
        print()

        # get properties in the form of a dictionary
        terminal_info_dict=mt5.terminal_info()._asdict()
        # convert the dictionary into DataFrame and print
        df=pd.DataFrame(list(terminal_info_dict.items()),columns=['property','value'])
        print("terminal_info() as dataframe:")
        print(df[:-1])

        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()
        ```

        ## Result:
        ```
        MetaTrader5 package author:  MetaQuotes Software Corp.
        MetaTrader5 package version:  5.0.29
        [500, 2367, '23 Mar 2020']
        TerminalInfo(community_account=True, community_connection=True, connected=True, dlls_allowed=False, trade_allowed=False, ...

        terminal_info() as dataframe:
                         property                         value
        0       community_account                          True
        1    community_connection                          True
        2               connected                          True
        3            dlls_allowed                         False
        4           trade_allowed                         False
        5       tradeapi_disabled                         False
        6           email_enabled                         False
        7             ftp_enabled                         False
        8   notifications_enabled                         False
        9                    mqid                         False
        10                  build                          2367
        11                maxbars                          5000
        12               codepage                          1251
        13              ping_last                         77881
        14      community_balance                       707.107
        15         retransmission                             0
        16                company     MetaQuotes Software Corp.
        17                   name                  MetaTrader 5
        18               language                       Russian
        19                   path  E:\ProgramFiles\MetaTrader 5
        20              data_path  E:\ProgramFiles\MetaTrader 5
        ```

        ## See also

            `initialize`, `shutdown`, `terminal_info`
        :rtype: Any

        """
        code = f'mt5.version(*{args},**{kwargs})'
        return self.__conn.eval(code)

    def eval(self, command: str) -> Any:
        r"""Evaluate a Python command in the remote MetaTrader 5 environment.

        :param command: 
        :type command: str
        :returns: Result of the evaluation.
        :rtype: Any

        """
        return self.__conn.eval(command)

    def execute(self, command: str) -> None:
        r"""Execute a Python command in the remote MetaTrader 5 environment.

        :param command: Python command as string.
        :type command: str
        :rtype: None

        """
        self.__conn.execute(command)

# Compatibilidade para importação direta
mt5 = MetaTrader5()
