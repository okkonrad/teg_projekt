# Użycie oficjalnego obrazu Pythona jako bazy
FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Ustawienie katalogu roboczego w kontenerze
WORKDIR /app

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

COPY . /app

WORKDIR /app

RUN uv sync --locked

# Otwarcie portu, na którym działa Streamlit (domyślnie 8501)
EXPOSE 8501

# Uruchomienie aplikacji Streamlit
ENTRYPOINT ["uv", "run", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]