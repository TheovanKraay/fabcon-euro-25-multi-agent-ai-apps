import openai
import streamlit as st
from openai import AzureOpenAI
import os
import numpy as np
import json
from datetime import datetime
import pandas as pd
from azure.cosmos import CosmosClient, exceptions, PartitionKey
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, AzureCliCredential
from dotenv import load_dotenv
import time
import requests

# Load environment variables - override system variables with .env file values
load_dotenv(override=True)

st.set_page_config(page_title="Ignite 2024 Demo", layout="wide", initial_sidebar_state="expanded")
# UI text strings
page_title = "Azure Cosmos DB - Search Demo"
page_helper = "Showcasing DiskANN (GA), full text search, text ranking, and hybrid search released at Ignite 2024."
empty_search_helper = "Enter text to get started."
semantic_search_header = "Search input"
semantic_search_placeholder = "James Bond"
vector_search_label = "Similarity search"
full_text_ranking_label = "Full text ranking"
full_text_search_label = "Full text search"
venue_list_header = "Research papers"
hybrid_search_label = "Hybrid search"

# Initialize global variables for Cosmos DB client, database, and containers
if "cosmos_client" not in st.session_state:
    endpoint = os.getenv("COSMOS_FABCON_URI")
    key = os.getenv("COSMOS_FABCON_KEY")
    
    # Check if endpoint is configured
    if not endpoint or endpoint == "your_cosmos_db_uri_here":
        st.error("❌ Cosmos DB endpoint not configured. Please update the .env file with your actual Cosmos DB URI.")
        st.info("💡 The app will work for reranker testing, but search functionality requires Cosmos DB endpoint.")
        st.session_state.cosmos_client = None
        st.session_state.cosmos_database = None
        st.session_state.cosmos_container_qflat = None
        st.session_state.cosmos_container_diskann = None
    else:
        try:
            # Determine authentication method
            if key and key != "your_cosmos_db_key_here":
                # Use key-based authentication
                st.info("🔑 Using key-based authentication for Cosmos DB")
                credential = key
            else:
                # Use DefaultAzureCredential for identity-based authentication
                st.info("🆔 Using DefaultAzureCredential for Cosmos DB (Managed Identity/Azure CLI)")
                credential = DefaultAzureCredential()
            
            st.session_state.cosmos_client = CosmosClient(endpoint, credential=credential)
            database_name = 'fabcon25demo'  # Replace with your database name
            st.session_state.cosmos_database = st.session_state.cosmos_client.create_database_if_not_exists(database_name)
            
            # Show success message with authentication method
            auth_method = "Key-based" if isinstance(credential, str) else "Identity-based"
            st.success(f"✅ Connected to Cosmos DB using {auth_method} authentication")
            
        except Exception as e:
            st.error(f"Failed to connect to Cosmos DB: {str(e)}")
            
            # Provide specific guidance based on authentication method
            if key and key != "your_cosmos_db_key_here":
                st.info("Please check your COSMOS_FABCON_URI and COSMOS_FABCON_KEY in the .env file")
            else:
                st.info("💡 Identity-based authentication failed. This could be because:")
                st.info("   • Azure CLI is not logged in (run 'az login')")
                st.info("   • Managed Identity is not configured properly")
                st.info("   • Your account doesn't have access to the Cosmos DB resource")
                st.info("   • Try providing COSMOS_FABCON_KEY in .env for key-based authentication")
            
            st.session_state.cosmos_client = None
            st.session_state.cosmos_database = None
            st.session_state.cosmos_container_qflat = None
            st.session_state.cosmos_container_diskann = None

    # Define the vector property and dimensions
    cosmos_vector_property = "embedding"
    cosmos_full_text_property = "text"
    openai_embeddings_dimensions = 1536

    # policies and indexes
    full_text_policy = {
        "defaultLanguage": "en-US",
        "fullTextPaths": [
            {
                "path": "/" + cosmos_full_text_property,
                "language": "en-US",
            }
        ]
    }
    vector_embedding_policy = {
        "vectorEmbeddings": [
            {
                "path": "/" + cosmos_vector_property,
                "dataType": "float32",
                "distanceFunction": "cosine",
                "dimensions": openai_embeddings_dimensions
            },
        ]
    }
    qflat_indexing_policy = {
        "includedPaths": [
            {"path": "/*"}
        ],
        "excludedPaths": [
            {"path": "/\"_etag\"/?"}
        ],
        "vectorIndexes": [
            {
                "path": "/" + cosmos_vector_property,
                "type": "quantizedFlat",
            }
        ],
        "fullTextIndexes": [
            {
                "path": "/" + cosmos_full_text_property
            }
        ]
    }

    diskann_indexing_policy = {
        "includedPaths": [
            {"path": "/*"}
        ],
        "excludedPaths": [
            {"path": "/\"_etag\"/?"}
        ],
        "vectorIndexes": [
            {
                "path": "/" + cosmos_vector_property,
                "type": "diskANN",
            }
        ],
        "fullTextIndexes": [
            {
                "path": "/" + cosmos_full_text_property
            }
        ]
    }

    # Create listings_search container without any index
    # container_name = 'search'
    # st.session_state.cosmos_container = st.session_state.cosmos_database.create_container_if_not_exists(
    #     id=container_name,
    #     partition_key=PartitionKey(path="/id"),
    #     full_text_policy=full_text_policy,
    #     vector_embedding_policy=vector_embedding_policy#,
    #     #offer_throughput=1000
    # )


    # Create containers only if we have a valid database connection
    if st.session_state.cosmos_database is not None:
        # Create listings_search_qflat container with QFLAT vector index
        container_name_qflat = 'search_qflat'
        st.session_state.cosmos_container_qflat = st.session_state.cosmos_database.create_container_if_not_exists(
            id=container_name_qflat,
            partition_key=PartitionKey(path="/id"),
            full_text_policy=full_text_policy,
            vector_embedding_policy=vector_embedding_policy,
            indexing_policy=qflat_indexing_policy,
            offer_throughput=400
        )

        # Create listings_search_diskann container with DiskANN vector index
        container_name_diskann = 'search_diskann'
        st.session_state.cosmos_container_diskann = st.session_state.cosmos_database.create_container_if_not_exists(
            id=container_name_diskann,
            partition_key=PartitionKey(path="/id"),
            full_text_policy=full_text_policy,
            vector_embedding_policy=vector_embedding_policy,
            indexing_policy=diskann_indexing_policy,
            offer_throughput=400
        )

# Initialize session state variables
if "embedding_gen_time" not in st.session_state:
    st.session_state.embedding_gen_time = ""
if "query_time" not in st.session_state:
    st.session_state.query_time = ""
if "ru_consumed" not in st.session_state:
    st.session_state.ru_consumed = ""
if "executed_query" not in st.session_state:
    st.session_state.executed_query = ""
if "server_query_time" not in st.session_state:
    st.session_state.server_query_time = ""

# Function to log times
def log_time(start):
    end = time.perf_counter()
    elapsed_time = end - start
    return f"{elapsed_time:.4f} seconds"

# Initialize the embedding client only once
if "embedding_client" not in st.session_state:
    try:
        st.session_state.embedding_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2023-05-15",
            azure_endpoint=os.getenv("OPENAI_ENDPOINT")
        )
    except TypeError as e:
        if "proxies" in str(e):
            # Fallback for Python 3.13 compatibility issues
            import httpx
            # Create a custom httpx client without the problematic arguments
            custom_client = httpx.Client()
            st.session_state.embedding_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version="2023-05-15",
                azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
                http_client=custom_client
            )
        else:
            raise e

# Handler functions
def embedding_query(text_input):
    print("text_input", text_input)
    start_time = time.perf_counter()
    response = st.session_state.embedding_client.embeddings.create(
        input=text_input,
        model="text-embedding-ada-002"  # Use the appropriate model
    )

    json_response = response.model_dump_json(indent=2)
    parsed_response = json.loads(json_response)
    embedding = parsed_response['data'][0]['embedding']
    st.session_state.embedding_gen_time = log_time(start_time)
    print(f"Embedding generation time: {st.session_state.embedding_gen_time}")
    return embedding

def get_reranker_credentials():
    """
    Get appropriate credentials for the reranker service based on the environment.
    For production: Use ManagedIdentityCredential with specific client_id
    For local development: Use AzureCliCredential with tenant_id
    """
    
    # Debug environment variables
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    print(f"🔍 Environment variables - AZURE_TENANT_ID: {tenant_id}")
    print(f"🔍 Environment variables - AZURE_CLIENT_ID: {client_id}")
    
    # Check if running in Azure (managed identity available)
    if os.getenv('MSI_ENDPOINT') or os.getenv('IDENTITY_ENDPOINT'):
        print("Running in Azure environment - using Managed Identity")
        if not client_id:
            raise ValueError("AZURE_CLIENT_ID environment variable is required for managed identity")
        return ManagedIdentityCredential(client_id=client_id)
    
    # For local development
    print("Running locally - using Azure CLI credential")
    if not tenant_id:
        raise ValueError("AZURE_TENANT_ID environment variable is required for local development")
    print(f"Note: Make sure you're logged in with 'az login --tenant {tenant_id}'")
    return AzureCliCredential(tenant_id=tenant_id)

def rerank_results(query, results_df, use_reranker=False):
    """
    Rerank search results using Azure's semantic reranker service.
    
    Args:
        query: The search query string
        results_df: DataFrame containing search results with 'text' column
        use_reranker: Boolean flag to enable/disable reranking
    
    Returns:
        DataFrame with reranked results (or original if reranker disabled/failed)
    """
    print(f"🔍 Reranker input - use_reranker: {use_reranker}")
    print(f"🔍 Reranker input - query: '{query}'")
    print(f"🔍 Reranker input - results_df shape: {results_df.shape if not results_df.empty else 'empty'}")
    print(f"🔍 Reranker input - results_df columns: {list(results_df.columns) if not results_df.empty else 'none'}")
    
    if not use_reranker or results_df.empty:
        print("🔍 Reranker skipped - either disabled or no results")
        return results_df
    
    try:
        # Get credentials and access token
        credentials = get_reranker_credentials()
        access_token = credentials.get_token("https://dbinference.azure.com/.default")
        
        headers = {
            "Authorization": f"Bearer {access_token.token}",
            "Content-Type": "application/json"
        }
        
        # Prepare documents for reranking
        documents = results_df['text'].tolist() if 'text' in results_df.columns else []
        
        print(f"🔍 Reranker input - documents count: {len(documents)}")
        if documents:
            print(f"🔍 Reranker input - first document preview: '{documents[0][:100]}...'")
        
        if not documents:
            print("No text content found in results for reranking")
            return results_df
        
        body = {
            "query": query,
            "documents": documents,
            "return_documents": True,
            "top_k": len(documents),  # Return all documents reranked
            "batch_size": 1
        }
        
        print(f"🔍 Reranker request body: {json.dumps(body, indent=2)[:500]}...")
        
        # Get reranker endpoint from environment
        reranker_endpoint = os.getenv("RERANKER_ENDPOINT")
        if not reranker_endpoint:
            print("⚠ RERANKER_ENDPOINT environment variable not set")
            return results_df
        
        # Make request to reranker service
        response = requests.post(
            reranker_endpoint, 
            headers=headers, 
            json=body
        )
        
        if response.status_code == 200:
            reranked_data = response.json()
            print(f"✓ Reranker response: {reranked_data}")
            
            # Handle the specific Azure reranker response format
            if 'Scores' in reranked_data:
                scores_data = reranked_data['Scores']
                print(f"✓ Found {len(scores_data)} scored documents in response")
                
                # The response already contains documents sorted by score
                # Each item in Scores is: {'document': 'text...', 'score': 0.99}
                reranked_df = pd.DataFrame()
                
                for i, score_item in enumerate(scores_data):
                    document_text = score_item.get('document', '')
                    score = score_item.get('score', 0)
                    
                    print(f"  Processing item {i+1}: score={score}, doc_preview='{document_text[:50]}...'")
                    
                    # Find the original row by matching text content exactly
                    # This preserves all original columns including ID, title, similarity scores, etc.
                    matching_rows = results_df[results_df['text'] == document_text]
                    
                    if len(matching_rows) > 0:
                        # Take the first match (should be unique)
                        original_row = matching_rows.iloc[0].copy()
                        
                        # Log what we're preserving from the original
                        original_id = original_row.get('id', 'N/A')
                        original_title = original_row.get('title', 'N/A')
                        print(f"    ✓ Matched with original ID: {original_id}, Title: '{str(original_title)[:30]}...'")
                        
                        # Add reranker score while preserving all other original data
                        original_row['reranker_score'] = score
                        original_row['reranker_rank'] = i + 1  # Add rank position for reference
                        
                        # Append to reranked DataFrame (maintaining reranker order)
                        reranked_df = pd.concat([reranked_df, original_row.to_frame().T], ignore_index=True)
                        
                    else:
                        print(f"    ⚠ Could not find matching row for document text")
                        print(f"        Looking for: '{document_text[:100]}...'")
                        print(f"        Available text previews in results_df:")
                        for idx, row in results_df.iterrows():
                            text_preview = str(row.get('text', ''))[:100]
                            print(f"          Row {idx}: '{text_preview}...'")
                
                if len(reranked_df) > 0:
                    print(f"✓ Successfully reranked {len(reranked_df)} results")
                    print(f"✓ Original columns preserved: {list(reranked_df.columns)}")
                    print(f"✓ Final order (by reranker): {list(reranked_df.get('id', ['N/A']*len(reranked_df)))}")
                    return reranked_df
                else:
                    print("⚠ Could not match any reranked results with original data")
                    print("⚠ Returning original results without reranking")
                    return results_df
                    
            # Fallback for other response formats
            elif 'results' in reranked_data:
                reranked_results = reranked_data['results']
                print(f"✓ Processing {len(reranked_results)} reranked results")
                # Create a new DataFrame with reranked order
                reranked_df = pd.DataFrame()
                
                for i, result in enumerate(reranked_results):
                    # Handle different result formats
                    document_text = None
                    score = None
                    
                    if isinstance(result, dict):
                        # Try different field names for document text
                        document_text = result.get('document') or result.get('text') or result.get('content')
                        score = result.get('score') or result.get('relevance_score') or result.get('similarity')
                    elif isinstance(result, str):
                        # Result might be just the document text
                        document_text = result
                    
                    if document_text:
                        # Find the original row by matching text content
                        original_idx = results_df[results_df['text'] == document_text].index
                        if len(original_idx) > 0:
                            reranked_row = results_df.loc[original_idx[0]].copy()
                            # Add reranker score if available
                            if score is not None:
                                reranked_row['reranker_score'] = score
                            else:
                                # Use position as implicit score (lower is better)
                                reranked_row['reranker_position'] = i + 1
                            reranked_df = pd.concat([reranked_df, reranked_row.to_frame().T], ignore_index=True)
                
                if len(reranked_df) > 0:
                    print(f"✓ Successfully reranked {len(reranked_df)} results")
                    return reranked_df
                else:
                    print("⚠ Could not match reranked results with original data")
                    return results_df
            else:
                print(f"⚠ Could not find Scores or results in reranker response. Available keys: {list(reranked_data.keys()) if isinstance(reranked_data, dict) else 'Response is not a dict'}")
                return results_df
        else:
            print(f"⚠ Reranker service returned status {response.status_code}: {response.text}")
            return results_df
            
    except Exception as e:
        print(f"⚠ Reranking failed: {e}")
        
        # Provide helpful error messages based on error type
        error_msg = str(e)
        if "Failed to invoke the Azure CLI" in error_msg:
            print("💡 Reranker authentication failed. This could be because:")
            print("   1. Azure CLI is not logged in")
            print("   2. Azure CLI is logged in to a different tenant")
            print("   3. Your account doesn't have access to the reranker service")
            print(f"   4. Try running: az login --tenant {os.getenv('AZURE_TENANT_ID', 'your-tenant-id')}")
            print("   5. Alternatively, disable the reranker checkbox to continue without reranking")
        elif "TimeoutExpired" in error_msg:
            print("💡 Azure CLI command timed out. Try:")
            print("   1. Check your network connection")
            print("   2. Try running 'az account show' to verify CLI status")
            print("   3. Disable the reranker checkbox to continue without reranking")
        
        import traceback
        traceback.print_exc()
        
        # Return original results when reranking fails
        print("🔄 Returning original search results without reranking")
        return results_df

def handler_vector_search(indices, ask):
    emb = embedding_query(ask)
    num_results = 10

    # Query strings
    vector_search_query = f'''
    SELECT TOP {num_results} l.id, l.title, l.text, VectorDistance(l.embedding, {emb}) as SimilarityScore
    FROM l
    ORDER BY VectorDistance(l.embedding,{emb})
    '''

    obfuscated_query = vector_search_query.replace(str(emb), "REDACTED")

    container = {
        #'No Index': st.session_state.cosmos_container,
        'QFLAT & Full Text Search Index': st.session_state.cosmos_container_qflat,
        'DiskANN & Full Text Search Index': st.session_state.cosmos_container_diskann
    }.get(indices)

    try:
        start_time = time.perf_counter()  # Capture start time
        st.session_state.executed_query = obfuscated_query
        results = container.query_items(vector_search_query, enable_cross_partition_query=True, populate_query_metrics=True)
        results_list = list(results)
        elapsed_time = log_time(start_time)
        
        # Create DataFrame from results
        results_df = pd.DataFrame(results_list)
        
        # Apply reranking if enabled
        use_reranker = st.session_state.get("use_reranker", False)
        if use_reranker:
            results_df = rerank_results(ask, results_df, use_reranker)
        
        st.session_state.suggested_listings = results_df
        st.session_state.query_time = elapsed_time
        st.session_state.ru_consumed = container.client_connection.last_response_headers['x-ms-request-charge']
        total_execution_time = parse_server_query_time(container.client_connection.last_response_headers['x-ms-documentdb-query-metrics'])
        st.session_state.server_query_time = total_execution_time
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"An error occurred: {e}")

def handler_text_search(indices, text, search_type):
    num_results = 10

    # Tokenize text into individual words
    keywords = text.split()  # Split the text into words
    formatted_keywords = ', '.join(f'"{keyword}"' for keyword in keywords)
    print(formatted_keywords)# Format keywords for query

    # Construct the query string with tokenized keywords
    if search_type == "all keywords":
        full_text_search_query = f'''
        SELECT TOP {num_results} l.id, l.title, l.text
        FROM l
        WHERE FullTextContainsAll(l.text, {formatted_keywords})
        '''
    else:
        full_text_search_query = f'''
        SELECT TOP {num_results} l.id, l.title, l.text
        FROM l
        WHERE FullTextContainsAny(l.text, {formatted_keywords})
        '''

    container = {
        #'No Index': st.session_state.cosmos_container,
        'QFLAT & Full Text Search Index': st.session_state.cosmos_container_qflat,
        'DiskANN & Full Text Search Index': st.session_state.cosmos_container_diskann
    }.get(indices)

    try:
        start_time = time.perf_counter()  # Capture start time
        st.session_state.executed_query = full_text_search_query
        results = container.query_items(full_text_search_query, enable_cross_partition_query=True, populate_query_metrics=True)
        results_list = list(results)
        elapsed_time = log_time(start_time)
        
        # Create DataFrame from results
        results_df = pd.DataFrame(results_list)
        
        # Apply reranking if enabled
        use_reranker = st.session_state.get("use_reranker", False)
        if use_reranker:
            results_df = rerank_results(text, results_df, use_reranker)
        
        st.session_state.suggested_listings = results_df
        st.session_state.query_time = elapsed_time
        st.session_state.ru_consumed = container.client_connection.last_response_headers['x-ms-request-charge']
        total_execution_time = parse_server_query_time(container.client_connection.last_response_headers['x-ms-documentdb-query-metrics'])
        st.session_state.server_query_time = total_execution_time
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"An error occurred: {e}")

def handler_text_ranking(indices, text):
    num_results = 10

    # Tokenize text into individual words
    keywords = text.split()  # Split the text into words
    formatted_keywords = ', '.join(f'"{keyword}"' for keyword in keywords)  # Format keywords for query

    # Construct the query string with tokenized keywords

    full_text_ranking_query = f'''
    SELECT TOP {num_results} l.id, l.title, l.text
    FROM l
    ORDER BY RANK FullTextScore(l.text, [{formatted_keywords}])
    '''

    container = {
        #'No Index': st.session_state.cosmos_container,
        'QFLAT & Full Text Search Index': st.session_state.cosmos_container_qflat,
        'DiskANN & Full Text Search Index': st.session_state.cosmos_container_diskann
    }.get(indices)

    try:
        start_time = time.perf_counter()  # Capture start time
        st.session_state.executed_query = full_text_ranking_query
        results = container.query_items(full_text_ranking_query, enable_cross_partition_query=True,populate_query_metrics=True)
        results_list = list(results)
        elapsed_time = log_time(start_time)
        
        # Create DataFrame from results
        results_df = pd.DataFrame(results_list)
        
        # Apply reranking if enabled
        use_reranker = st.session_state.get("use_reranker", False)
        if use_reranker:
            results_df = rerank_results(text, results_df, use_reranker)
        
        st.session_state.suggested_listings = results_df
        st.session_state.query_time = elapsed_time
        st.session_state.ru_consumed = container.client_connection.last_response_headers['x-ms-request-charge']
        total_execution_time = parse_server_query_time(container.client_connection.last_response_headers['x-ms-documentdb-query-metrics'])
        st.session_state.server_query_time = total_execution_time
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"An error occurred: {e}")

def handler_hybrid_ranking(indices, text):
    num_results = 10
    emb = embedding_query(text)
    # Tokenize text into individual words
    keywords = text.split()  # Split the text into words
    formatted_keywords = ', '.join(f'"{keyword}"' for keyword in keywords)  # Format keywords for query

    # Construct the query string with tokenized keywords

    full_hybrid_ranking_query = f'''
    SELECT TOP {num_results} l.id, l.title, l.text
    FROM l
    ORDER BY RANK RRF(FullTextScore(l.text,[{formatted_keywords}]),VectorDistance(l.embedding, {emb}))
    '''

    obfuscated_query = full_hybrid_ranking_query.replace(str(emb), "REDACTED")

    container = {
        #'No Index': st.session_state.cosmos_container,
        'QFLAT & Full Text Search Index': st.session_state.cosmos_container_qflat,
        'DiskANN & Full Text Search Index': st.session_state.cosmos_container_diskann
    }.get(indices)

    try:
        start_time = time.perf_counter()  # Capture start time
        st.session_state.executed_query = obfuscated_query
        results = container.query_items(full_hybrid_ranking_query, enable_cross_partition_query=True,populate_query_metrics=True)
        results_list = list(results)
        elapsed_time = log_time(start_time)
        
        # Create DataFrame from results
        results_df = pd.DataFrame(results_list)
        
        # Apply reranking if enabled
        use_reranker = st.session_state.get("use_reranker", False)
        if use_reranker:
            results_df = rerank_results(text, results_df, use_reranker)
        
        st.session_state.suggested_listings = results_df
        st.session_state.query_time = elapsed_time
        st.session_state.ru_consumed = container.client_connection.last_response_headers['x-ms-request-charge']
        total_execution_time = parse_server_query_time(container.client_connection.last_response_headers['x-ms-documentdb-query-metrics'])
        st.session_state.server_query_time = total_execution_time
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"An error occurred: {e}")

# UI elements
def render_cta_link(url, label, font_awesome_icon):
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">',
        unsafe_allow_html=True)
    button_code = f'''<a href="{url}" target=_blank><i class="fa {font_awesome_icon}"></i> {label}</a>'''
    return st.markdown(button_code, unsafe_allow_html=True)

def parse_server_query_time(query_metrics):
    metrics_parts = query_metrics.split(";")
    total_execution_time_ms = next(
        (part.split("=")[1] for part in metrics_parts if "totalExecutionTimeInMs" in part), "0"
    )
    total_execution_time_s = float(total_execution_time_ms) / 1000
    return f"{total_execution_time_s:.4f} seconds"

def render_search():
    search_disabled = True
    with st.sidebar:
        st.selectbox(label="Index", options=['No Index', 'QFLAT & Full Text Search Index', 'DiskANN & Full Text Search Index'], index=0, key="index_selection")
        st.text_input(label=semantic_search_header, placeholder=semantic_search_placeholder, key="user_query")
        
        # Add reranker checkbox
        st.checkbox("Use Semantic Reranker", key="use_reranker", help="Apply semantic reranking to search results using Azure's reranker service")

        if "user_query" in st.session_state and st.session_state.user_query != "":
            search_disabled = False

        st.button(label=vector_search_label, key="location_search", disabled=search_disabled,
                  on_click=handler_vector_search, args=(st.session_state.index_selection, st.session_state.user_query))

        # Button for Full Text Ranking search using handler_text_ranking
        st.button(label=full_text_ranking_label, key="full_text_ranking", disabled=search_disabled,
                  on_click=handler_text_ranking, args=(st.session_state.index_selection, st.session_state.user_query))

        # Button for Hybrid Ranking search using handler_hybrid_ranking
        st.button(label=hybrid_search_label, key="hybrid_search", disabled=search_disabled,
                  on_click=handler_hybrid_ranking, args=(st.session_state.index_selection, st.session_state.user_query))

        search_type = st.radio("Search type", options=["all keywords", "any keywords"], key="full_text_search_type")

        st.button(label=full_text_search_label, key="full_text_search", disabled=search_disabled,
                  on_click=handler_text_search, args=(st.session_state.index_selection, st.session_state.user_query, search_type))



        st.write("---")
        render_cta_link(url="https://azurecosmosdb.github.io/gallery/", label="Cosmos DB Samples Gallery", font_awesome_icon="fa-cosmosdb")
        render_cta_link(url="https://github.com/AzureCosmosDB/BRK193-Ignite2024/cosmos-search-demo", label="GitHub", font_awesome_icon="fa-github")

def render_search_result():
    col1 = st.container()
    col1.write(f"Executed query: {st.session_state.executed_query}")
    col1.write(f"Embedding generation time: {st.session_state.embedding_gen_time}")
    col1.write(f"Total end-to-end query execution time: {st.session_state.query_time}")
    col1.write(f"Total server query execution time: {st.session_state.server_query_time}")
    col1.write(f"RU consumed: {st.session_state.ru_consumed}")
    
    # Show reranker status
    use_reranker = st.session_state.get("use_reranker", False)
    reranker_applied = use_reranker and "reranker_score" in st.session_state.suggested_listings.columns
    col1.write(f"Semantic reranking: {'✓ Applied' if reranker_applied else '✗ Not applied'}")
    
    col1.write(f"Found {len(st.session_state.suggested_listings)} records.")
    col1.table(st.session_state.suggested_listings)

# Main execution
render_search()

st.title(page_title)
st.write(page_helper)
st.write("---")

if "suggested_listings" not in st.session_state:
    st.write(empty_search_helper)
else:
    render_search_result()