#!/bin/bash

echo "🍕 Pizza Microservices Demo - Run Script"
echo "========================================"
echo ""

echo "🚀 Starting demo application..."
echo ""

# Run the application using Docker Compose
docker compose up -d --build

# Check if Docker Compose command succeeded
if [ $? -ne 0 ]; then
    echo "❌ Failed to start the application with Docker Compose"
    exit 1
fi

echo "✅ Setup complete!"
echo "🌐 Web application: http://localhost:8000"
echo ""
echo "🛑 To stop the application, run: docker compose down"
echo "🗑️  To destroy the Terraform infrastructure and clean up resources, run: ./destroy-demo.sh"
echo ""
