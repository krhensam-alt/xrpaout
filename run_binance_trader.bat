@echo off
set SELECTED_EXCHANGE=BINANCE
set MOCK_MODE=True
echo ===================================================
echo   XRP AI TRADER SYSTEM (BINANCE VERSION) STARTING...
echo ===================================================
echo Selected Exchange: %SELECTED_EXCHANGE%
echo.
python -m uvicorn backend.main:app --host 0.0.0.0 --port 13151 --reload
pause
