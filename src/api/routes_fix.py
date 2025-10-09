"""Fix datetime serialization in routes.py"""

with open('src/api/routes.py', 'r') as f:
    lines = f.readlines()

# Find and fix line 292 (return JSONResponse)
fixed_lines = []
for i, line in enumerate(lines, 1):
    if i == 292 and 'return JSONResponse(content=response_data)' in line:
        # Replace with serialized version
        fixed_lines.append('        # Serialize datetime objects\n')
        fixed_lines.append('        from src.schemas.base_schemas import serialize_for_json\n')
        fixed_lines.append('        return JSONResponse(content=serialize_for_json(response_data))\n')
    else:
        fixed_lines.append(line)

with open('src/api/routes.py', 'w') as f:
    f.writelines(fixed_lines)

print("✅ Fixed datetime serialization in routes.py")
