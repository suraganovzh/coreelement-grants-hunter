"""
Test Telegram notifications locally.

Usage:
    python scripts/test_notifications.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set env vars for testing
os.environ['TELEGRAM_BOT_TOKEN'] = input("Enter bot token: ")
os.environ['TELEGRAM_CHAT_ID'] = input("Enter chat ID: ")
os.environ['DASHBOARD_URL'] = 'https://suraganovzh.github.io/coreelement-grants-hunter'

from scripts.send_telegram_notifications import send_message, send_daily_digest, load_grants

print("\n🧪 Testing Telegram notifications...\n")

# Test 1: Simple message
print("Test 1: Sending test message...")
if send_message("✅ Test message from Grant Hunter AI"):
    print("✅ Success\n")
else:
    print("❌ Failed\n")
    sys.exit(1)

# Test 2: Daily digest
print("Test 2: Sending daily digest...")
grants = load_grants()
if grants:
    send_daily_digest(grants)
    print("✅ Success\n")
else:
    print("⚠️ No grants data found (data/analyzed.json missing)\n")

print("✅ All tests completed!")
