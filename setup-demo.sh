#!/bin/bash

echo "🍕 Pizza Microservices Demo - Setup Script"
echo "=========================================="
echo ""

# Check prerequisites
echo "🛂 Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed. Please install Terraform."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker."
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Check .env file exists
echo "🔑 Validating credentials..."
if [ ! -f ".env" ]; then
    echo "❌ .env file not found"
    echo "   Please create '.env' file with Confluent Cloud credentials, see file .env_example for reference"
    exit 1
fi

# Load environment variables from .env
source .env

if [ -z "$CONFLUENT_CLOUD_API_KEY" ] || [ -z "$CONFLUENT_CLOUD_API_SECRET" ]; then
    echo "❌ Confluent Cloud credentials not found in .env file"
    echo "   Required: CONFLUENT_CLOUD_API_KEY and CONFLUENT_CLOUD_API_SECRET"
    echo "   Please create '.env' file with Confluent Cloud credentials, see file .env_example for reference"
    exit 1
fi

echo "✅ Credentials validated"
echo ""

# Terraform infrastructure setup
echo "🏗️ Setting up Confluent Cloud infrastructure with Terraform..."
cd terraform

echo "🔧 Initializing Terraform..."
terraform init
if [ $? -ne 0 ]; then
    echo "❌ Terraform init failed"
    cd ..
    exit 1
fi

echo ""
echo "📋 Planning Terraform deployment..."
terraform plan
if [ $? -ne 0 ]; then
    echo "❌ Terraform plan failed"
    cd ..
    exit 1
fi

echo ""
echo "⚙️ Applying Terraform configuration..."
terraform apply -auto-approve
if [ $? -ne 0 ]; then
    echo "❌ Terraform apply failed"
    cd ..
    exit 1
fi

echo "✅ Confluent Cloud infrastructure created"
echo ""
cd ..

echo "✅ Setup complete!"
echo ""

echo "Next step:"
echo "▶️ Start the demo: ./run-demo.sh"
echo ""
