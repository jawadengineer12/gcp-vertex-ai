import os

# 1. Enforce Airtight Environment Bindings before imports
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "config/gcp-sa-key.json"
os.environ["GCP_PROJECT"] = "indesign-layout-ai"
os.environ["GCP_LOCATION"] = "us-central1"

from google import genai
from google.genai import types

try:
    print("Initiating regionalized cloud handshake with Gemini via Vertex AI...")
    
    # 2. Strict Initialization Signature
    client = genai.Client(
        vertexai=True,
        project="indesign-layout-ai",
        location="us-central1"
    )
    
    # 3. Request layout verification from the regional endpoint cluster
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Hello Vertex AI! Connection confirmed for InDesign layout pipeline mapping.',
    )
    
    print("\n[SUCCESS] Gateway active! Response from cloud model:")
    print(f"👉 {response.text.strip()}")

except Exception as e:
    print(f"\n[ERROR] Connection failed. Trace inspection detail:\n{e}")