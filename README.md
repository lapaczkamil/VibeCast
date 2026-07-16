# VibeCast

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify and OpenAI keys in `.env` when needed. Never commit `.env`.

## Run

```bash
source .venv/bin/activate
uvicorn main:app --reload
```

Status: [http://127.0.0.1:8000/status](http://127.0.0.1:8000/status)
