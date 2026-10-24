@echo off
REM Reconstruit Recharges-VE.exe avec icone et ressources embarquees.
REM Double-cliquez ce fichier (ou lancez-le depuis un terminal) apres
REM avoir ferme l'application.

cd /d "%~dp0"
echo Reconstruction de Recharges-VE.exe ...
REM Depuis la 2.0.0, l'interface est en PySide6 (Qt), comme Pecule et le
REM Photovoltaique : l'exe est donc plus gros (environ 250 Mo au lieu de 93).
REM fleche_bas.svg (et fleche_bas_sombre.svg, pour le mode sombre) est la
REM fleche des listes deroulantes (theme_qt.py) : sans
REM elle, les listes n'ont plus de fleche, sans aucune erreur. L'autotest
REM verifie qu'elle est bien livree.
REM Les --exclude-module retirent ce que l'application n'utilise pas :
REM tkinter et customtkinter (l'ancienne interface), PyQt (matplotlib le
REM detecte sur le PC), pandas (tire par openpyxl sans servir), pytest.
REM
REM « py » et non « python » : c'est « py » qui lance l'application depuis les
REM sources et les tests ; en construisant avec lui, l'exe embarque exactement
REM les bibliotheques que l'autotest a verifiees.
REM
REM L'ancien programme est retire d'abord : si la construction echoue, sa
REM seule presence faisait afficher « Termine » (audit du 14/10/2026). Seul
REM le dossier du programme part ; les donnees, a cote dans dist\, restent.
REM
REM Version publique : « build.bat public ». La saisie depuis le telephone
REM est reservee a la version privee (decision du 24/10/2026) : ses modules
REM sont alors laisses hors de l'exe, et l'application n'en montre plus rien
REM (constantes.SAISIE_TELEPHONE). preparer_distribution.py et
REM faire_installeur.py refusent un exe qui les contient encore.
set EXCLUSIONS_PRIVEES=
if /i "%~1"=="public" set EXCLUSIONS_PRIVEES=--exclude-module telephone --exclude-module fenetre_telephone --exclude-module segno
if /i "%~1"=="public" echo Version PUBLIQUE : sans la saisie depuis le telephone.
if exist "dist\Recharges-VE" rmdir /s /q "dist\Recharges-VE"
if exist "dist\Recharges-VE" (
  echo ECHEC : l'ancien programme n'a pas pu etre retire. L'application
  echo est-elle encore ouverte ? Fermez-la, puis relancez ce fichier.
  pause
  exit /b 1
)
py -m PyInstaller --noconfirm --onedir --windowed ^
  --name "Recharges-VE" ^
  --icon "icone_voiture.ico" ^
  --add-data "icone_voiture.ico;." ^
  --add-data "fleche_bas.svg;." ^
  --add-data "fleche_bas_sombre.svg;." ^
  --collect-all reportlab ^
  --collect-submodules openpyxl ^
  --exclude-module tkinter ^
  --exclude-module customtkinter ^
  --exclude-module PyQt5 ^
  --exclude-module PyQt6 ^
  --exclude-module pandas ^
  --exclude-module pytest ^
  %EXCLUSIONS_PRIVEES% ^
  app.py

REM Le code de retour de PyInstaller : 0 si tout s'est bien passe.
if errorlevel 1 (
  echo.
  echo ECHEC : la construction a echoue, verifiez les messages ci-dessus.
  pause
  exit /b 1
)
if not exist "dist\Recharges-VE\Recharges-VE.exe" (
  echo.
  echo ECHEC : l'exe n'a pas ete produit, verifiez les messages ci-dessus.
  pause
  exit /b 1
)

echo.
echo Termine : dist\Recharges-VE\Recharges-VE.exe
echo.
echo Verification automatique ^(toutes les pages + les exports^) ...
REM « start /wait » : l'exe est une application fenetree, sans lui le script
REM n'attendrait pas la fin de l'autotest et ne connaitrait pas son resultat.
if exist "%TEMP%\recharges_autotest.txt" del "%TEMP%\recharges_autotest.txt"
start "" /wait "dist\Recharges-VE\Recharges-VE.exe" --autotest "%TEMP%\recharges_autotest.txt"
set RESULTAT_AUTOTEST=%errorlevel%
if exist "%TEMP%\recharges_autotest.txt" type "%TEMP%\recharges_autotest.txt"
echo.
if not "%RESULTAT_AUTOTEST%"=="0" (
  echo ECHEC : la verification automatique a trouve un probleme ^(voir ci-dessus^).
  pause
  exit /b 1
)
echo Verification automatique reussie.
pause
