import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Check API key
ncbi_key = os.getenv('NCBI_API_KEY')

print("=" * 60)
print("NCBI API Key Configuration Check")
print("=" * 60)

if ncbi_key:
    print(f"✅ API Key Found: {ncbi_key[:8]}...{ncbi_key[-4:]}")
    print(f"   Length: {len(ncbi_key)} characters")
    print(f"   Status: CONFIGURED")
    print(f"\n🚀 You can make 10 requests/second (3.3x faster)")
else:
    print("❌ API Key Not Found")
    print("   Check .env file for NCBI_API_KEY variable")
    print("   Status: USING DEFAULT (3 req/sec)")

print("=" * 60)