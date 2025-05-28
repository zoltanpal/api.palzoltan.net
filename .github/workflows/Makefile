PROJECT_DIR := /var/www/api.palzoltan.net
VENV := $(PROJECT_DIR)/.venv
SERVICE ?= api.palzoltan.net.service
USER := www-data

.PHONY: all prepare restart download-nltk download-model setup deploy

all: setup restart

prepare:
	@echo "▶ Ensuring required folders exist..."
	sudo mkdir -p $(PROJECT_DIR)/.cache
	sudo mkdir -p $(PROJECT_DIR)/nltk_data
	sudo chown -R $(USER):$(USER) $(PROJECT_DIR)/.cache
  sudo chown -R 777 $(PROJECT_DIR)/.cache
	sudo chown -R $(USER):$(USER) $(PROJECT_DIR)/nltk_data
  sudo chown -R 777 $(PROJECT_DIR)/nltk_data

download-nltk:
	@echo "▶ Downloading NLTK resources..."
	sudo -u $(USER) bash -c '\
		source $(VENV)/bin/activate && \
		export NLTK_DATA=$(PROJECT_DIR)/nltk_data && \
		python -c "import nltk; nltk.download(\"stopwords\"); nltk.download(\"punkt\")" \
	'

download-model:
	@echo "▶ Downloading Hugging Face model..."
	sudo -u $(USER) bash -c '\
		source $(VENV)/bin/activate && \
		export TRANSFORMERS_CACHE=$(PROJECT_DIR)/.cache && \
		python -c "from transformers import AutoModel; AutoModel.from_pretrained(\"NYTK/sentiment-hts5-xlm-roberta-hungarian\")" \
	'

restart:
	@echo "▶ Restarting systemd service..."
	sudo systemctl restart $(SERVICE)

setup: prepare download-nltk download-model

deploy: setup restart
