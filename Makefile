.PHONY: run

run:
	poetry run uvicorn main:app --reload