FROM python:alpine

WORKDIR /app

COPY main.py .
COPY requirements.txt .
COPY platforms ./platforms

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root user
ARG user_id=3045
RUN addgroup -g ${user_id} -S inventoryst && adduser -u ${user_id} -S -G inventoryst inventoryst
USER inventoryst

CMD [ "python", "/app/main.py" ]
