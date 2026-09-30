FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-u", "run_bot.py", "--mode", "LIVE", "--risk", "0.02", "--leverage", "5", "--max-positions", "1"]
