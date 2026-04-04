#!/usr/bin/env python3
"""
Script to create and test the ScholarMate custom model
"""
import subprocess
import sys

def create_model():
    """Create the custom ScholarMate model using Ollama"""
    print("🔧 Creating ScholarMate custom model...")
    
    result = subprocess.run(
        ["ollama", "create", "scholarmate", "-f", "models/ScholarMate.Modelfile"],
        cwd="C:\\Users\\fudha\\Desktop\\scholarflow\\backend",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Model created successfully!")
        return True
    else:
        print(f"❌ Error: {result.stderr}")
        return False

def test_model():
    """Test the custom model"""
    print("\n🧪 Testing ScholarMate model...")
    
    test_prompt = "Explain the transformer architecture in 3 sentences using academic tone."
    
    result = subprocess.run(
        ["ollama", "run", "scholarmate", test_prompt],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"\n📝 Response:\n{result.stdout}")
        return True
    else:
        print(f"❌ Error: {result.stderr}")
        return False

if __name__ == "__main__":
    if create_model():
        test_model()
