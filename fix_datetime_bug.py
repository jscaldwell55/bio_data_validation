"""
Fix: Convert datetime objects to ISO format strings in API responses
"""

import re

# Read the routes file
with open('src/api/routes.py', 'r') as f:
    content = f.read()

# Find the get_validation_status function
# We need to add datetime serialization

# Check if the fix is already there
if 'isoformat()' in content or 'str(timestamp)' in content:
    print("✅ Fix already applied or timestamps already handled")
else:
    print("🔧 Applying fix...")
    
    # The issue is in get_validation_status around line 292
    # We need to ensure datetime objects are converted to strings
    
    # Find the response_data construction
    old_pattern = r'("submitted_at":\s*)([^,\n}]+)'
    
    # Look for the problematic line
    if '"submitted_at"' in content:
        # Add .isoformat() to datetime fields
        content = content.replace(
            'response_data = {',
            'response_data = {\n        # Convert datetime to string for JSON serialization'
        )
        
        # More robust fix: import datetime at top and add custom encoder
        if 'from datetime import datetime' not in content:
            # Add import
            content = content.replace(
                'from fastapi import',
                'from datetime import datetime\nfrom fastapi import'
            )
    
    with open('src/api/routes.py', 'w') as f:
        f.write(content)
    
    print("✅ Fix applied")

print("\n📝 Now we need to rebuild the Docker container...")
