.PHONY: run

run:
	poetry run uvicorn main:app --reload --port 8080

.PHONY: export
export:
	poetry export -f requirements.txt --without dev --output requirements.txt

.PHONY: build
build:
	make export
	docker build -t asia-northeast1-docker.pkg.dev/cyberagent-285/dialogue-demo/dialogue_demo_image:latest -f Dockerfile .