# FABCON Europe 2025 Search Demo with Azure Cosmos DB + Semantic Reranking

This repository contains a Python Streamlit application that demonstrates advanced search capabilities using Azure Cosmos DB, OpenAI embeddings, and Azure's semantic reranker service. The application showcases vector search, full text search, text ranking, and hybrid search with intelligent semantic reranking to improve result relevance.

![screenshot](media/screen-shot.png)

## ✨ Features

- **Multi-Modal Search Integration** with Azure Cosmos DB:
  - 🔍 **Semantic search** for movies using OpenAI embeddings
  - 📝 **Full text search** with advanced text processing
  - 🔄 **Hybrid search** combining semantic and full text search
  - 📊 **Text ranking** for enhanced result ordering
- **🎯 Semantic Reranking** (NEW):
  - Integration with Azure's semantic reranker service
  - Interactive UI toggle to enable/disable reranking
  - Preserves original metadata while improving result relevance
  - Smart authentication handling for local and Azure environments
- **📈 Multiple Index Support**:
  - No Index baseline
  - QFLAT vector index for balanced performance
  - DiskANN vector index for high-scale scenarios
- **🛡️ Robust Error Handling**:
  - Graceful credential validation
  - Helpful troubleshooting messages
  - Fallback modes when services are unavailable
- **🎨 Interactive UI** built with Streamlit

## Prerequisites

- [Azure Cosmos DB](https://azure.microsoft.com/services/cosmos-db/) account with NoSQL API
- [Azure OpenAI](https://azure.microsoft.com/products/ai-services/openai-service) account
- **Azure semantic reranker service** (for enhanced result ranking)
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) (for local reranker authentication)

## 🚀 Quick Start

### 1. Clone and Setup

```sh
git clone https://github.com/TheovanKraay/fabcon-euro-25-multi-agent-ai-apps.git
cd fabcon-euro-25-multi-agent-ai-apps/cosmos-search-demo
```

### 2. Configure Environment Variables

Copy the template and configure your credentials:

```sh
cp src/app/.env.template src/app/.env
```

Edit `src/app/.env` with your actual Azure service credentials:

```env
# Azure Cosmos DB Configuration
COSMOS_FABCON_URI=https://your-cosmos-db.documents.azure.com:443/
COSMOS_FABCON_KEY=your_cosmos_db_key_here

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ENDPOINT=https://your-openai.openai.azure.com/

# Azure Identity Configuration for Reranker
AZURE_TENANT_ID=your_tenant_id_here
AZURE_CLIENT_ID=your_client_id_here
RERANKER_ENDPOINT=https://your-reranker.dbinference.azure.com/inference/semanticReranking
```

### 3. Install Dependencies

```sh
pip install -r src/app/requirements.txt
```

### 4. Authenticate for Reranker (Local Development)

For semantic reranking to work locally:

```sh
az login --tenant your_tenant_id_here
```

### 5. Run the Application

```sh
streamlit run src/app/cosmos-app.py
```

## 🎯 Using the Semantic Reranker

The application now includes Azure's semantic reranker service for improved search relevance:

### Features:
- **Smart Ranking**: Reorders search results based on semantic similarity to your query
- **UI Toggle**: Enable/disable reranking with the checkbox in the sidebar
- **Metadata Preservation**: Maintains all original result data (IDs, titles, scores)
- **Robust Authentication**: Automatic credential handling for local and Azure environments

### How to Use:
1. **Check the "Use Semantic Reranker" checkbox** in the sidebar
2. **Perform any search** (vector, text, or hybrid)
3. **Compare results** with and without reranking enabled

### Troubleshooting Reranker:
- **Authentication Issues**: Ensure you're logged in with `az login --tenant <your-tenant-id>`
- **Service Access**: Verify your account has access to the reranker service
- **Fallback Mode**: App continues working even if reranking fails

## 📁 Project Structure

```
cosmos-search-demo/
├── src/
│   ├── app/
│   │   ├── cosmos-app.py          # Main Streamlit application
│   │   ├── reranker.py           # Standalone reranker demo
│   │   ├── requirements.txt      # Python dependencies
│   │   ├── .env.template         # Environment variable template
│   │   └── .env                  # Your credentials (not in git)
│   └── data/
│       ├── data-loader.py        # Data ingestion script
│       └── drop-containers.py    # Container cleanup utility
├── README.md
└── .gitignore
```

## 🔧 Advanced Configuration

### Environment Variables Reference:

| Variable | Description | Required |
|----------|-------------|----------|
| `COSMOS_FABCON_URI` | Azure Cosmos DB endpoint | ✅ |
| `COSMOS_FABCON_KEY` | Azure Cosmos DB key | ✅ |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | ✅ |
| `OPENAI_ENDPOINT` | Azure OpenAI endpoint | ✅ |
| `AZURE_TENANT_ID` | Azure tenant ID for reranker | 🎯 |
| `AZURE_CLIENT_ID` | Azure client ID for reranker | 🎯 |
| `RERANKER_ENDPOINT` | Semantic reranker service endpoint | 🎯 |

*🎯 = Required for semantic reranking feature*

### Authentication Modes:
- **Local Development**: Uses Azure CLI authentication (`AzureCliCredential`)
- **Azure Deployment**: Uses Managed Identity authentication (`ManagedIdentityCredential`)
- **Automatic Detection**: Switches based on environment (MSI_ENDPOINT presence)

## 🚀 Deploy to Azure with VS Code

### Prerequisites:
- Azure subscription with App Service capabilities
- VS Code with Azure App Service extension

### Steps:

1. **Install the Azure App Service extension**:
   - Open Extensions view (Ctrl+Shift+X)
   - Search for "Azure App Service" and install

2. **Create Azure Web App**:
   - Create [Azure Web App](https://learn.microsoft.com/azure/app-service/overview) 
   - Use Linux service plan (B1 SKU or higher)
   - Select Python 3.10+ runtime

3. **Configure App Service**:
   - Go to Configuration → General Settings
   - Set **Startup Command**:
     ```shell
     python -m pip install -r src/app/requirements.txt && python -m streamlit run src/app/cosmos-app.py --server.port 8000 --server.address 0.0.0.0
     ```
   - Add environment variables in Configuration → Application Settings

4. **Deploy**:
   - Press Ctrl+Shift+P
   - Select "Azure App Service: Deploy to Web App"
   - Select this project folder
   - Choose your subscription and Web App
   - Wait for deployment (up to 5 minutes)

### 🔐 Production Security:
- Use **Managed Identity** for Azure service authentication
- Store sensitive values in **Azure Key Vault**
- Configure **Application Settings** instead of .env files

## 📊 Loading Data into Cosmos DB

The app automatically creates containers with proper vector and text search policies. Use the data loader to populate with your data:

### Basic Usage:
```sh
cd src/data
python data-loader.py \
  --text_field_name "overview" \
  --path_to_json_array "your-data.json" \
  --database_name "fabcon25demo" \
  --concurrency 20 \
  --re_embed True
```

### Movie Dataset Example:
```sh
python src/data/data-loader.py \
  --text_field_name "overview" \
  --path_to_json_array "https://raw.githubusercontent.com/microsoft/AzureDataRetrievalAugmentedGenerationSamples/refs/heads/main/DataSet/Movies/MovieLens-4489-256D.json" \
  --database_name "fabcon25demo" \
  --concurrency 20 \
  --vector_field_name "vector" \
  --re_embed True
```

### 🗑️ Container Management:
Use the cleanup utility to remove containers:
```sh
python src/data/drop-containers.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support & Troubleshooting

### Common Issues:

**❌ "Failed to connect to Cosmos DB"**
- Verify `COSMOS_FABCON_URI` and `COSMOS_FABCON_KEY` in .env
- Check network connectivity to Azure

**❌ "Reranking failed: Failed to invoke the Azure CLI"**
- Run: `az login --tenant <your-tenant-id>`
- Verify Azure CLI is installed and updated

**❌ "No results found"**
- Ensure data is loaded into Cosmos containers
- Check container names match the app configuration

### Performance Tips:
- Use **DiskANN index** for large datasets (>100K documents)
- Use **QFLAT index** for balanced performance and cost
- Adjust **concurrency** in data loader based on Cosmos DB throughput

### 📞 Need Help?
- Check the [Issues](https://github.com/TheovanKraay/fabcon-euro-25-multi-agent-ai-apps/issues) page
- Review Azure Cosmos DB [documentation](https://docs.microsoft.com/azure/cosmos-db/)
- Consult Azure OpenAI [best practices](https://docs.microsoft.com/azure/cognitive-services/openai/)
