
import sys
import os
import logging

# Add backend to path so we can import app modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.logging import setup_logging

def verify_logging():
    print(f"Original stdout encoding: {sys.stdout.encoding}")
    
    # Setup logging (this should reconfigure stdout/stderr)
    logger = setup_logging()
    
    print(f"Reconfigured stdout encoding: {sys.stdout.encoding}")
    
    try:
        logger.info("Test log with simple text")
        logger.info("Test log with emoji: ✅")
        logger.info("Test log with rocket: 🚀")
        print("✅ VERIFICATION SUCCESSFUL: Logging with emojis worked!")
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        raise

if __name__ == "__main__":
    verify_logging()
