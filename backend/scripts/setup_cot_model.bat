@echo off
REM Quick setup script for Chain-of-Thought models
REM Run this from: C:\Users\fudha\Desktop\scholarflow\backend\

echo.
echo ====================================================================
echo  Chain-of-Thought Model Setup for ScholarFlow
echo ====================================================================
echo.

REM Check if Ollama is running
echo [1/4] Checking if Ollama is running...
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Ollama is not running!
    echo.
    echo Please start Ollama first:
    echo   - Click Start Menu and search for "Ollama"
    echo   - Or run: ollama serve
    echo.
    pause
    exit /b 1
)
echo ✓ Ollama is running

REM Check if base model exists
echo.
echo [2/4] Checking if base model (llama3.2:3b) exists...
ollama list | find "llama3.2:3b" >nul
if %errorlevel% neq 0 (
    echo ⚠️  Base model not found. Pulling llama3.2:3b (this may take a few minutes)...
    ollama pull llama3.2:3b
    if %errorlevel% neq 0 (
        echo ❌ Failed to pull base model
        pause
        exit /b 1
    )
)
echo ✓ Base model exists

REM Create CoT model
echo.
echo [3/4] Creating scholarmate-cot model...
if exist "models\ScholarMate-CoT.Modelfile" (
    cd models
    ollama create scholarmate-cot -f ScholarMate-CoT.Modelfile
    cd ..
    if %errorlevel% neq 0 (
        echo ❌ Failed to create model
        pause
        exit /b 1
    )
    echo ✓ scholarmate-cot model created
) else (
    echo ❌ ScholarMate-CoT.Modelfile not found
    echo.
    echo Make sure you're in the backend directory with the models folder
    pause
    exit /b 1
)

REM Verify model
echo.
echo [4/4] Verifying model installation...
ollama list | find "scholarmate-cot" >nul
if %errorlevel% neq 0 (
    echo ❌ Model verification failed
    pause
    exit /b 1
)
echo ✓ Model verified

echo.
echo ====================================================================
echo ✅ Setup Complete!
echo ====================================================================
echo.
echo Next steps:
echo.
echo 1. Update configuration:
echo    - Open backend/app/core/config.py
echo    - Change: ollama_model_smart: str = "scholarmate"
echo    - To:     ollama_model_smart: str = "scholarmate-cot"
echo.
echo 2. Optional: Update backend/.env
echo    OLLAMA_MODEL_SMART=scholarmate-cot
echo    ENABLE_COT_REASONING=true
echo    SHOW_THINKING_TO_USER=false
echo.
echo 3. Restart the backend:
echo    python -m uvicorn app.main:app --reload --port 8000
echo.
echo 4. Test it works:
echo    python tests/test_chain_of_thought.py
echo.
echo For detailed instructions, see: ENABLE_COT_QUICK_START.md
echo.
pause
