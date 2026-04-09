@echo off
cd /d "%~dp0"
echo ================================================
echo   Lcloud PC — Build Lcloud.exe
echo ================================================
echo.

cd lcloud-pc
if not exist venv\Scripts\activate (
    echo [ERROR] venv not found. Run lcloud-pc\setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate

REM Generate icon
python -c "
from PIL import Image, ImageDraw, ImageFont
sizes = [16,32,48,64,128,256]
imgs = []
for s in sizes:
    img = Image.new('RGBA',(s,s),(0,0,0,0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(0,0),(s-1,s-1)],radius=s//5,fill='#4f46e5')
    try: f=ImageFont.truetype('arialbd.ttf',int(s*0.6))
    except: f=ImageFont.load_default()
    bb=d.textbbox((0,0),'L',font=f)
    d.text(((s-(bb[2]-bb[0]))//2-bb[0],(s-(bb[3]-bb[1]))//2-bb[1]),'L',fill='white',font=f)
    imgs.append(img)
imgs[0].save('src/lcloud.ico',format='ICO',sizes=[(s,s) for s in sizes],append_images=imgs[1:])
print('[OK] Icon generated')
"

echo Building Lcloud.exe...
pyinstaller --name "Lcloud" --noconsole --onefile ^
  --icon src\lcloud.ico ^
  --paths src ^
  --collect-data customtkinter ^
  --collect-data pystray ^
  --hidden-import zeroconf._handlers.answers ^
  --hidden-import zeroconf._utils.ipaddress ^
  --hidden-import zeroconf._dns ^
  src\main.py

if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

copy /y dist\Lcloud.exe ..\Lcloud.exe >nul
echo.
echo ================================================
echo   Built: Lcloud.exe
for %%F in ("..\Lcloud.exe") do echo   Size: %%~zF bytes
echo   Double-click Lcloud.exe to launch the app.
echo ================================================
pause
