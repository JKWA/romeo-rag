IMAGE_NAME=romeo-rag
CONTAINER_NAME=romeo-rag-container
PORT=8002
VENV_DIR=venv
SENTENCES_PER_CHUNK ?= 30
OVERLAP ?= 10
QUERY ?= "Is this a sad story?"
N_RESULTS ?= 10

.PHONY: build run stop logs setup run-local

setup:
	python3 -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install -r requirements.txt

reset-data:
	$(VENV_DIR)/bin/python -m settings $(SENTENCES_PER_CHUNK) $(OVERLAP)

test-query:
	$(VENV_DIR)/bin/python -m search $(QUERY) $(N_RESULTS)

run-local:
	$(VENV_DIR)/bin/flask  run  --debug



