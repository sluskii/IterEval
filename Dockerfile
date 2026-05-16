FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    grep -v "^pytest\|^torch" requirements.txt | pip install --no-cache-dir -r /dev/stdin

COPY . .

ENV PYTHONPATH=/app
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8501

CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
