FROM python:3.10

WORKDIR /app

RUN sudo apt-get install git && \
                        ffmpeg

RUN git clone https://github.com/obahamonde/XTTS.git && pip install -e ./XTTS

RUN COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]