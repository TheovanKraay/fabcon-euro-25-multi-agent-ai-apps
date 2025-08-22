
import requests
import json
import os

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, AzureCliCredential

def get_credentials():
    """
    Get appropriate credentials based on the environment.
    For production: Use ManagedIdentityCredential with specific client_id
    For local development: Use AzureCliCredential with tenant_id
    """
    
    # Check if running in Azure (managed identity available)
    if os.getenv('MSI_ENDPOINT') or os.getenv('IDENTITY_ENDPOINT'):
        print("Running in Azure environment - using Managed Identity")
        return ManagedIdentityCredential(client_id="73c5c9a8-adb0-4bb2-8094-0223eee837f1")
    
    # For local development
    print("Running locally - using Azure CLI credential")
    print("Note: Make sure you're logged in with 'az login --tenant c946e397-b5fa-4e25-a3c5-cda19b56d781'")
    return AzureCliCredential(tenant_id="c946e397-b5fa-4e25-a3c5-cda19b56d781")

try:
    credentials = get_credentials()
    access_token = credentials.get_token("https://dbinference.azure.com/.default")
    print(f"✓ Authentication successful")
    print(f"  Token expires at: {access_token.expires_on}")
    
except Exception as e:
    print(f"✗ Authentication failed: {e}")
    print("\nTroubleshooting steps:")
    print("1. Run: az login --tenant c946e397-b5fa-4e25-a3c5-cda19b56d781")
    print("2. Ensure your account has access to the dbinference service")
    exit(1)

headers = {
    "Authorization": f"Bearer {access_token.token}",
    "Content-Type": "application/json"
}

body = {
    "query": "What is the capital of France?",
    "documents": [
        "Berlin is the capital of Germany.",
        "Paris is the capital of France.",
        "Madrid is the capital of Spain."
    ],
    "return_documents": True,
    "top_k": 10,
    "batch_size": 1
}

response = requests.post("https://tvkreranker.dbinference.azure.com/inference/semanticReranking", headers=headers, json=body)

print(f"Making request to: {response.url}")
print(f"Request headers: {headers}")

if response.status_code != 200:
    print(f"\n✗ Request failed with status {response.status_code}")
    print(f"Response text: {response.text}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 403:
        print("\n🔍 403 Forbidden - Possible causes:")
        print("1. Your account doesn't have access to this reranker endpoint")
        print("2. The reranker 'tvkreranker' might not be registered for your account")
        print("3. You might need to register with the service first")
        print("4. The managed identity needs to be granted access to the reranker")
        
elif response.status_code == 200:
    print(f"✓ Success: {json.loads(response.content)}")
else:
    print(f"⚠ Unexpected status code {response.status_code}: {response.text}")
