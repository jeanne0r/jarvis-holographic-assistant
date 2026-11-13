FROM python:3.12-slim
WORKDIR /app
COPY semantic/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY semantic/service.py ./service.py
RUN useradd --create-home --uid 10001 jarvis && mkdir /models && chown jarvis:jarvis /models
USER jarvis
EXPOSE 6335
CMD ["uvicorn","service:app","--host","0.0.0.0","--port","6335","--no-access-log"]
