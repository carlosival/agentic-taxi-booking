# myapp/Dockerfile 

#Preinstall linux with python and uv
FROM python:3.12-slim-bookworm


# Working Dir on Docker guest continer 
WORKDIR /app

# Copy project files (prefer specific copy of project metadata before full source)
COPY requirements.txt .

# Dockerfile - Install additional libraries needed by psycopg2
RUN apt-get update && apt-get install -y libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

# Install dependencies using uv (equivalent of `pip install`)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run your app (FastAPI example)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]