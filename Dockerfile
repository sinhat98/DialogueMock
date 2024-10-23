FROM asia-northeast1-docker.pkg.dev/cyberagent-285/aim-app/mecab_image:latest

RUN apt-get update && apt-get install -y \
    libsndfile1 libsndfile-dev

ENV PATH=$PATH:/root/.cargo/bin
RUN curl https://sh.rustup.rs -sSf > /rust.sh && \
    chmod +x /rust.sh && \
    sh /rust.sh -y

# COPY pyproject.toml poetry.lock ./
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# pip install poetry &&  \
# poetry lock && \
# poetry export -f requirements.txt --output requirements.txt && \

COPY . .


EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]