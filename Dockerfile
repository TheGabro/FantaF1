FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Raccolta statici in fase di build (non richiede il database).
# SECRET_KEY fittizia solo per far caricare i settings durante la build.
RUN SECRET_KEY="build-only-not-a-secret" python manage.py collectstatic --noinput

EXPOSE 8000

# All'avvio: applica le migrazioni e serve l'app con gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn FantaF1.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
