from config import config

# 거래소 선택 로직
if config.SELECTED_EXCHANGE == "BINANCE":
    from binance_client import binance_client
    exchange_client = binance_client
    CURRENCY_UNIT = "USDT"
    PRICE_UNIT = "USDT"
    MIN_ORDER_VALUE = 10.0 # USDT
else:
    from upbit_client import upbit_client
    exchange_client = upbit_client
    CURRENCY_UNIT = "원"
    PRICE_UNIT = "KRW"
    MIN_ORDER_VALUE = 5000 # KRW
