@echo off
chcp 65001 > nul
echo ================================================================================
echo  ADY201m - CHAY TOAN BO PIPELINE 7 BUOC (NHOM 8 - NTSB ACCIDENT SEVERITY)
echo ================================================================================
echo.

echo [1/7] Dang chay Buoc 1: Data Understanding...
python 01_data_understanding.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 1! & pause & exit /b %ERRORLEVEL%)
echo.

echo [2/7] Dang chay Buoc 2: Data Cleaning...
python 02_data_cleaning.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 2! & pause & exit /b %ERRORLEVEL%)
echo.

echo [3/7] Dang chay Buoc 3: SQL Analysis...
python 03_sql_analysis.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 3! & pause & exit /b %ERRORLEVEL%)
echo.

echo [4/7] Dang chay Buoc 4: Feature Engineering & Temporal Split...
python 04_feature_engineering_split.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 4! & pause & exit /b %ERRORLEVEL%)
echo.

echo [5/7] Dang chay Buoc 5: Evidence-Based Visualizations...
python 05_visualization.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 5! & pause & exit /b %ERRORLEVEL%)
echo.

echo [6/7] Dang chay Buoc 6: Severity Modeling (5 Models x 5 Seeds)...
python 06_modeling_evaluation.py
if %ERRORLEVEL% NEQ 0 (echo Lỗi ở Bước 6! & pause & exit /b %ERRORLEVEL%)
echo.

echo [7/7] Dang chay Buoc 7: Kiem tra Dashboard Tool...
python 07_dashboard_app.py
echo.
echo ================================================================================
echo  DA HOAN TAT TAT CA CAC BUOC!
echo  De mo Dashboard tren trinh duyet Web, hay go lenh:
echo      python -m streamlit run 07_dashboard_app.py
echo ================================================================================
pause
