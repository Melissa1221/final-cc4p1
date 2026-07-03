@echo off
REM Compila y corre el Cliente Vigilante (Java + FlatLaf) en Windows.
REM Uso: scripts\correr-vigilante.bat   (desde la raiz del repo)
set RAIZ=%~dp0..
set JAVA=%RAIZ%\java
set JAR=%JAVA%\lib\flatlaf-3.4.1.jar

if not exist "%JAVA%\out" mkdir "%JAVA%\out"
javac -cp "%JAR%" -d "%JAVA%\out" "%JAVA%\src\vigilante\Vigilante.java"
java -cp "%JAVA%\out;%JAR%" vigilante.Vigilante
