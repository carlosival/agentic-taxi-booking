#!/usr/bin/env bash
set -euo pipefail

# === CONFIGURATION ===
# List of required environment variables
REQUIRED_VARS=(
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_DB
  RABBITMQ_USER
  RABBITMQ_PASSWORD
  REDIS_PASSWORD
  WHATSAPP_TOKEN
  TELEGRAM_TOKEN
  MINIO_USER
  MINIO_PASSWORD
)

# === FUNCTIONS ===
error() {
  echo "❌ ERROR: $1" >&2
  exit 1
}

check_env_vars() {
  echo "🔍 Checking required environment variables..."
  for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
      error "Missing required environment variable: $var"
    fi
  done
  echo "✅ All required environment variables are set."
}

create_or_update_secret() {
  local name="$1"
  local value="$2"

  if echo -n "$value" | docker secret create "$name" - 2>/dev/null; then
    echo "🆕 Created secret: $name"
  else
    echo "♻️  Updating secret: $name"
    docker secret rm "$name" >/dev/null 2>&1 || true
    echo -n "$value" | docker secret create "$name" -
  fi
}

# === MAIN SCRIPT ===
check_env_vars

echo "🔐 Creating or updating Docker Swarm secrets..."
create_or_update_secret postgres_user "$POSTGRES_USER"
create_or_update_secret postgres_password "$POSTGRES_PASSWORD"
create_or_update_secret postgres_db "$POSTGRES_DB"
create_or_update_secret rabbitmq_user "$RABBITMQ_USER"
create_or_update_secret rabbitmq_password "$RABBITMQ_PASSWORD"
create_or_update_secret redis_password "$REDIS_PASSWORD"
create_or_update_secret whatsapp_token "$WHATSAPP_TOKEN"
create_or_update_secret telegram_token "$TELEGRAM_TOKEN"

echo "✅ All secrets have been created or updated successfully."