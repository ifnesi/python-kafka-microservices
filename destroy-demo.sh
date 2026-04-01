#!/bin/bash

echo "🍕 Pizza Microservices Demo - Destroy Script"
echo "============================================"
echo ""
echo "⚠️  WARNING: This will destroy all Confluent Cloud resources!"
echo ""

# Confirmation prompt
read -p "Are you sure you want to proceed? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Destroy cancelled"
    exit 0
fi

echo ""

# Stop Docker containers if running
echo "🛑 Stopping Docker containers..."
docker compose down
echo "✅ Docker containers stopped"
echo ""

# Load environment variables from .env
source .env

cd terraform
echo ""
echo "🗑️ Destroying Confluent Cloud infrastructure with Terraform..."
terraform destroy -auto-approve
if [ $? -ne 0 ]; then
    echo "❌ Terraform destroy failed"
    exit 1
fi

cd ..
echo "✅ Confluent Cloud infrastructure destroyed"
echo ""

echo "✅ Confluent Cloud resources have been cleaned up. You can now safely delete the .env file if you wish."
echo ""
