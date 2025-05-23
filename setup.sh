#!/bin/bash
set -e

# Create directory structure
echo "Creating directory structure..."
mkdir -p app/core app/models app/providers app/repositories app/services app/api/routes tests

# Initialize files with empty content to create proper structure
touch app/__init__.py
touch app/core/__init__.py
touch app/models/__init__.py
touch app/providers/__init__.py
touch app/repositories/__init__.py
touch app/services/__init__.py
touch app/api/__init__.py
touch app/api/routes/__init__.py

# Create alembic directory for migrations
mkdir -p alembic/versions
touch alembic/README
touch alembic/script.py.mako

# Initialize git repository
echo "Initializing git repository..."
git init
git add .
git commit -m "Initial commit: Project structure setup"

echo "Setting up virtual environment..."
# Check if uv is installed, if not, install it
if ! command -v uv &> /dev/null
then
    echo "Installing uv package manager..."
    pip install uv
fi

# Create virtual environment using uv
uv venv

# Activate virtual environment
echo "To activate the virtual environment:"
echo "  source venv/bin/activate  # On Unix/macOS"
echo "  .\\venv\\Scripts\\activate  # On Windows"

echo "To install dependencies:"
echo "  uv pip install -r requirements.txt"

echo "To initialize the database:"
echo "  alembic revision --autogenerate -m 'Initial migration'"
echo "  alembic upgrade head"

echo "Setup complete!"
