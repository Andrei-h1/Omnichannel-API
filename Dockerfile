# ============================
# 1. BASE IMAGE
# ============================
FROM python:3.11-slim

# ============================
# 2. SYSTEM DEPENDENCIES
# ============================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ============================
# 3. WORKDIR
# ============================
WORKDIR /app

# ============================
# 4. INSTALL PYTHON DEPENDENCIES
# ============================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================
# 5. COPY SOURCE CODE
# ============================
COPY . .

# ============================
# 6. EXPOSE
# ============================
EXPOSE 8000

# ============================
# 7. ENTRYPOINT
# ============================
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
