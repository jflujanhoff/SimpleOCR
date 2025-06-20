#!/usr/bin/env python3
"""
Debug script for OpenAI API JSON parsing issues.
Run this script to diagnose the OpenAI connection problem.
"""

import os
import json
import base64
from PIL import Image
import io
import openai
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_openai_connection():
    """Test OpenAI connection step by step."""
    
    print("=" * 60)
    print("OpenAI API Debug Script")
    print("=" * 60)
    
    # Step 1: Check API key
    print("\n1. Checking API key...")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable is not set")
        return False
    
    print(f"✅ API key found (length: {len(api_key)})")
    
    if not api_key.startswith('sk-'):
        print("⚠️  Warning: API key doesn't start with 'sk-'")
    else:
        print("✅ API key format looks correct")
    
    # Step 2: Initialize client
    print("\n2. Initializing OpenAI client...")
    try:
        client = openai.OpenAI(api_key=api_key)
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Step 3: Test basic API call
    print("\n3. Testing basic API connection...")
    try:
        models = client.models.list()
        print(f"✅ Basic API call successful. Found {len(models.data)} models")
    except Exception as e:
        print(f"❌ Basic API call failed: {e}")
        return False
    
    # Step 4: Test text-only chat completion
    print("\n4. Testing text-only chat completion...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=10
        )
        print(f"✅ Text chat completion successful: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Text chat completion failed: {e}")
        return False
    
    # Step 5: Create test image
    print("\n5. Creating test image...")
    try:
        # Create a simple 10x10 white image
        test_image = Image.new('RGB', (10, 10), color='white')
        
        # Convert to base64
        buffered = io.BytesIO()
        test_image.save(buffered, format="JPEG", quality=85)
        img_bytes = buffered.getvalue()
        base64_str = base64.b64encode(img_bytes).decode('utf-8')
        
        print(f"✅ Test image created (base64 length: {len(base64_str)})")
    except Exception as e:
        print(f"❌ Failed to create test image: {e}")
        return False
    
    # Step 6: Test vision API with minimal request
    print("\n6. Testing vision API...")
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_str}"
                        }
                    }
                ]
            }
        ]
        
        # Validate JSON serialization
        json_test = json.dumps(messages)
        print(f"✅ Message structure validation passed (JSON length: {len(json_test)})")
        
        # Make the API call
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=50
        )
        
        print(f"✅ Vision API test successful: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Vision API test failed: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Additional debugging for the specific error
        if "JSON body" in str(e):
            print("\n🔍 JSON parsing error detected. Additional debugging:")
            print(f"   - Base64 length: {len(base64_str)}")
            print(f"   - First 50 chars of base64: {base64_str[:50]}")
            print(f"   - Last 50 chars of base64: {base64_str[-50:]}")
            
            # Check for invalid characters
            import string
            valid_chars = string.ascii_letters + string.digits + '+/='
            invalid_chars = [c for c in base64_str if c not in valid_chars]
            if invalid_chars:
                print(f"   - Invalid base64 characters found: {set(invalid_chars)}")
            else:
                print("   - Base64 string contains only valid characters")
        
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! OpenAI API is working correctly.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    test_openai_connection() 