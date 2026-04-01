#!/bin/bash

echo "🍕 Pizza Microservices Demo - Stop Script"
echo "============================================"
echo ""

# Stop Docker containers if running
echo "🛑 Stopping Docker containers..."
docker compose down
echo "✅ Docker containers stopped"
echo ""

cd ..
echo "✅ Demo stopped successfully. You can now run ./destroy-demo.sh to clean up Confluent Cloud resources if you wish."
echo ""
