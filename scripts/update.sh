#!/bin/bash
# Quick Update Script für Proxmox

echo "🔄 Updating Offer Ghost..."

# Pull latest code
git pull origin main

# Rebuild & Restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "✅ Update complete!"
docker-compose logs -f --tail=20
