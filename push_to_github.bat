@echo off
chcp 65001 >nul
echo ========================================================
echo   ĐẨY CODE LÊN GITHUB REPOSITORY - NHÓM 8 ADY201m
echo   Repo: https://github.com/Lementledge/Group8_ADY201m_FA26_AI2108
echo ========================================================
echo.
echo Đang kiểm tra trạng thái Git...
"C:\Users\ASUS\AppData\Local\github-copilot-git-2.53.0-4\cmd\git.exe" status
echo.
echo Đang thực hiện git push lên main...
echo (Lưu ý: Trình duyệt hoặc cửa sổ Git sẽ mở để bạn bấm Authorize / Đăng nhập GitHub)
echo.
"C:\Users\ASUS\AppData\Local\github-copilot-git-2.53.0-4\cmd\git.exe" push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [THÀNH CÔNG] Code đã được đẩy lên GitHub thành công!
) else (
    echo [CHÚ Ý] Nếu bạn muốn đẩy bằng Personal Access Token (PAT), hãy chạy lệnh:
    echo git remote set-url origin https://TOKEN@github.com/Lementledge/Group8_ADY201m_FA26_AI2108.git
    echo git push -u origin main
)
pause
