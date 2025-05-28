#!/bin/bash

set -e

ENV="$1"

if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
  echo "❌ Usage: $0 [dev|prod]"
  exit 1
fi

if [ "$ENV" == "prod" ]; then
  PROJECT_DIR="/var/www/sandbox/prod"
else
  PROJECT_DIR="/var/www/sandbox/dev"
fi

VENV="$PROJECT_DIR/.venv"
NLTK_DATA="$PROJECT_DIR/nltk_data"
TRANSFORMERS_CACHE="$PROJECT_DIR/.cache"

echo "▶ Preparing environment: $ENV"
echo "▶ Project directory: $PROJECT_DIR"
echo "▶ Service: $SERVICE_NAME"

# Create and fix folder permissions
echo "▶ Ensuring folders exist and have correct permissions..."
sudo mkdir -p "$NLTK_DATA" "$TRANSFORMERS_CACHE"
sudo chown -R www-data:www-data "$NLTK_DATA" "$TRANSFORMERS_CACHE"

# Download NLTK resources
echo "▶ Downloading NLTK resources..."
sudo -u www-data bash -c "
  source '$VENV/bin/activate' && \
  export NLTK_DATA='$NLTK_DATA' && \
  python -c \"import nltk; nltk.download('stopwords'); nltk.download('vader_lexicon'); nltk.download('punkt')\"
"

# Download Hugging Face model
echo "▶ Downloading transformer model..."
sudo -u www-data bash -c "
  source '$VENV/bin/activate' && \
  export TRANSFORMERS_CACHE='$TRANSFORMERS_CACHE' && \
  python -c \"from transformers import AutoModel; AutoModel.from_pretrained('NYTK/sentiment-hts5-xlm-roberta-hungarian')\"
"

echo "✅ Setup completed for $ENV"
