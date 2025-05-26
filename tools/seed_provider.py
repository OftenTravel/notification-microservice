#!/usr/bin/env python3
"""
Provider Seeding Tool

This script interactively collects provider information and seeds it to the database.
Run this script directly to add a new provider to the database.
"""
import asyncio
import json
import os
import sys
from typing import List, Dict, Any

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import AsyncSessionLocal
from app.repositories.provider_repository import ProviderRepository


async def get_text_input(prompt: str, default: str = None) -> str:
    """Get text input with optional default value."""
    default_prompt = f" [{default}]" if default else ""
    value = input(f"{prompt}{default_prompt}: ").strip()
    if not value and default:
        return default
    return value


async def get_bool_input(prompt: str, default: bool = None) -> bool:
    """Get boolean input with optional default value."""
    default_str = "y/N" if default is False else "Y/n" if default is True else "y/n"
    value = input(f"{prompt} [{default_str}]: ").strip().lower()
    
    if not value and default is not None:
        return default
    return value.startswith('y')


async def get_int_input(prompt: str, default: int = None) -> int:
    """Get integer input with optional default value and validation."""
    while True:
        default_prompt = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{default_prompt}: ").strip()
        
        if not value and default is not None:
            return default
            
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid number")


async def get_list_input(prompt: str, options: List[str] = None, 
                        default: List[str] = None) -> List[str]:
    """Get list input with optional default value."""
    if options:
        options_str = ", ".join(options)
        print(f"Available options: {options_str}")
        
    default_str = ", ".join(default) if default else "none"
    value_str = input(f"{prompt} [comma-separated, {default_str}]: ").strip()
    
    if not value_str and default:
        return default
        
    return [item.strip() for item in value_str.split(',') if item.strip()]


async def get_json_input(prompt: str, default: Dict = None) -> Dict:
    """Get JSON input with validation."""
    default_str = json.dumps(default, indent=2) if default else "{}"
    print(f"{prompt} (enter valid JSON):")
    print(f"Default: {default_str}")
    print("Enter JSON (finish with empty line):")
    
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    
    json_str = "\n".join(lines).strip()
    
    if not json_str and default:
        return default
        
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print("Invalid JSON. Using default.")
        return default or {}


async def seed_provider():
    """Interactively collect provider data and add to database."""
    print("\n===== Provider Seeding Tool =====\n")
    
    # Collect provider information
    name = await get_text_input("Provider name (e.g., msg91, twilio, sendgrid)")
    
    # Check if provider already exists
    async with AsyncSessionLocal() as db:
        repo = ProviderRepository(db)
        existing = await repo.get_provider_by_name(name)
        
        if existing:
            print(f"Provider '{name}' already exists with ID: {existing.id}")
            update = await get_bool_input("Update existing provider?", default=False)
            if not update:
                print("Operation cancelled.")
                return
    
    # Get provider details
    supported_types = await get_list_input(
        "Supported notification types",
        options=["sms", "email", "whatsapp"],
        default=["sms", "email", "whatsapp"]
    )
    
    priority = await get_int_input("Priority (lower is higher priority)", default=10)
    is_active = await get_bool_input("Is active?", default=True)
    
    # Default configs based on provider type
    default_config = {}
    if name == "msg91":
        default_config = {
            "api_key": "your-api-key-here",
            "sender_id": "NOTIFY", 
            "email_from": "no-reply@example.com",
            "email_from_name": "Notification Service"
        }
    elif name == "twilio":
        default_config = {
            "account_sid": "your-sid-here",
            "auth_token": "your-token-here",
            "from_number": "+123456789"
        }
    elif name == "mock":
        default_config = {
            "success_rate": 0.95,
            "delay_ms": 500
        }
        
    config = await get_json_input("Provider configuration", default=default_config)
    
    # Collect the provider data
    provider_data = {
        "name": name,
        "supported_types": supported_types,
        "is_active": is_active,
        "priority": priority,
        "config": config
    }
    
    # Confirm before saving
    print("\n----- Provider Details -----")
    print(f"Name: {name}")
    print(f"Types: {', '.join(supported_types)}")
    print(f"Priority: {priority}")
    print(f"Active: {'Yes' if is_active else 'No'}")
    print("Config:")
    print(json.dumps(config, indent=2))
    print("--------------------------\n")
    
    confirm = await get_bool_input("Save this provider?", default=True)
    if not confirm:
        print("Operation cancelled.")
        return
        
    # Save to database
    async with AsyncSessionLocal() as db:
        repo = ProviderRepository(db)
        
        if existing:
            await repo.update_provider(existing.id, provider_data)
            print(f"Provider '{name}' updated successfully!")
        else:
            provider = await repo.create_provider(provider_data)
            print(f"Provider '{name}' created successfully with ID: {provider.id}")


if __name__ == "__main__":
    try:
        asyncio.run(seed_provider())
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"\nError: {str(e)}")
