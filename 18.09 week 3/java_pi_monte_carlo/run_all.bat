@echo off
REM =====================================================================
REM  Monte Carlo Pi - Concurrency Benchmark Suite  (plain cmd.exe)
REM
REM  Usage:  run_all.bat
REM
REM  This is the fallback runner. It uses no PowerShell semantics, so it
REM  is immune to the stderr-becomes-an-error behaviour that can trip up
REM  a .ps1 script.
REM =====================================================================

setlocal enabledelayedexpansion

if not exist out     mkdir out
if not exist results mkdir results

set "OUT=results\benchmark_output.txt"
set "TMPF=%TEMP%\pi_part_out.txt"

echo.
echo =======================================================================
echo  Monte Carlo Pi - Concurrency Benchmark Suite
echo =======================================================================
echo.

REM ---- check for a JDK ------------------------------------------------
where javac >nul 2>&1
if errorlevel 1 (
    echo javac was not found on your PATH.
    echo A JRE alone is not enough - this needs a full JDK.
    echo Check with:  java -version   and   javac -version
    exit /b 1
)

REM ---- banner ----------------------------------------------------------
> "%OUT%" echo =======================================================================
>>"%OUT%" echo  MONTE CARLO PI - CONCURRENCY BENCHMARK SUITE
>>"%OUT%" echo =======================================================================
>>"%OUT%" echo  Run timestamp : %DATE% %TIME%
>>"%OUT%" echo  Machine       : %COMPUTERNAME%
>>"%OUT%" echo =======================================================================
>>"%OUT%" echo.

echo Collecting hardware info...
wmic cpu get name,NumberOfCores,NumberOfLogicalProcessors /format:list >> "%OUT%" 2>&1
java -version >> "%OUT%" 2>&1
>>"%OUT%" echo.

REM ---- compile ---------------------------------------------------------
echo Compiling...
javac -d out src\Part1PhantomBug.java src\Part2SynchronizationTrap.java src\Part3Reduction.java
if errorlevel 1 (
    echo COMPILATION FAILED - fix the errors above before continuing.
    exit /b 1
)
echo Compiled OK.
echo.

REM ---- run the three parts --------------------------------------------
call :runpart Part1PhantomBug          "PART 1 - The Phantom Bug"
call :runpart Part2SynchronizationTrap "PART 2 - The Synchronization Trap"
call :runpart Part3Reduction           "PART 3 - OpenMP-Style Reduction"

if exist part3_results.csv move /Y part3_results.csv results\part3_results.csv >nul

>>"%OUT%" echo.
>>"%OUT%" echo =======================================================================
>>"%OUT%" echo  SUITE COMPLETE - %DATE% %TIME%
>>"%OUT%" echo =======================================================================

echo.
echo All done.
echo Transcript : %CD%\%OUT%
if exist results\part3_results.csv echo Part 3 CSV : %CD%\results\part3_results.csv
echo.
exit /b 0

REM ---------------------------------------------------------------------
:runpart
set "CLS=%~1"
set "LABEL=%~2"
echo Running %LABEL% ...

>>"%OUT%" echo.
>>"%OUT%" echo #######################################################################
>>"%OUT%" echo # %LABEL%
>>"%OUT%" echo # command: java -cp out %CLS%
>>"%OUT%" echo # started: %TIME%
>>"%OUT%" echo #######################################################################
>>"%OUT%" echo.

java -cp out %CLS% > "%TMPF%" 2>&1
type "%TMPF%"
type "%TMPF%" >> "%OUT%"
echo   done.
echo.
exit /b 0
