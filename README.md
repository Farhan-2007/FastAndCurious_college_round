# FastAndCurious_college_round

## Backend API

### Local setup

Run these commands from the project root on Windows:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r backend\requirements.txt
python -m pip install -r ai_core\requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000