.PHONY: run

run:
	poetry run uvicorn main:app --reload --port 8080

.PHONY: export
export:
	poetry export -f requirements.txt --without dev --without-hashes --output requirements.txt

.PHONY: build
build:
	make export
	docker buildx build --platform linux/amd64 --load -t asia-northeast1-docker.pkg.dev/cyberagent-285/dialogue-demo/dialogue_demo_image:latest -f Dockerfile .

.PHONY: build-clean
build-clean:
	make export
	docker buildx build --no-cache --platform linux/amd64 --load -t asia-northeast1-docker.pkg.dev/cyberagent-285/dialogue-demo/dialogue_demo_image:latest -f Dockerfile .

# bashの起動
.PHONY: bash
bash:
	docker run -it --rm asia-northeast1-docker.pkg.dev/cyberagent-285/dialogue-demo/dialogue_demo_image:latest /bin/bash

.PHONY: push
push:
	docker push asia-northeast1-docker.pkg.dev/cyberagent-285/dialogue-demo/dialogue_demo_image:latest