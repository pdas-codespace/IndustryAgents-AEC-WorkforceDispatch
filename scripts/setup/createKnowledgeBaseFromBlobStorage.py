#!/usr/bin/env python3
"""
Create an Azure AI Search Knowledge Base with Azure Blob Storage as Knowledge Source

This script demonstrates how to:
1. Create a search index with vector and semantic search capabilities
2. Create a data source connection to Azure Blob Storage
3. Create an indexer to ingest documents from Blob Storage
4. Create a knowledge source pointing to the search index
5. Create a knowledge base that wraps the knowledge source for agentic retrieval

Prerequisites:
- Azure AI Search service with agentic retrieval support
- Azure Blob Storage with documents (PDF, DOCX, etc.)
- Azure OpenAI with text-embedding model deployed
- Azure AI Search managed identity must have 'Storage Blob Data Reader' role on the storage account
- Proper role assignments (see README.md)

Reference: https://github.com/Azure-Samples/azure-search-python-samples/blob/main/agentic-retrieval-pipeline-example/agent-example.ipynb
"""

import os
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    # Index components
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    # Data source components
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
    # Indexer components
    SearchIndexer,
    IndexingParameters,
    IndexingParametersConfiguration,
    # Skillset components
    SearchIndexerSkillset,
    SplitSkill,
    AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    # Knowledge base components
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
    SearchIndexFieldReference,
    KnowledgeBase,
    KnowledgeSourceReference,
    KnowledgeRetrievalOutputMode,
    KnowledgeRetrievalMinimalReasoningEffort,
)
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "workforce-documents")
KNOWLEDGE_SOURCE_NAME = os.getenv("AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME", "workforce-knowledge-source")
KNOWLEDGE_BASE_NAME = os.getenv("AZURE_SEARCH_KNOWLEDGE_BASE_NAME", "workforce-knowledge-base")

# Azure Blob Storage (using Entra ID authentication)
BLOB_STORAGE_RESOURCE_ID = os.environ["AZURE_BLOB_STORAGE_RESOURCE_ID"]  # e.g., /subscriptions/.../resourceGroups/.../providers/Microsoft.Storage/storageAccounts/<name>
BLOB_CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER_NAME", "workforce-documents")

# Azure OpenAI (for embeddings)
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AZURE_OPENAI_EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))

# Initialize credential
credential = DefaultAzureCredential()


def create_search_index(index_client: SearchIndexClient) -> None:
    """
    Create a search index with vector search and semantic configuration.
    
    The index is optimized for:
    - Chunked document content
    - Vector embeddings for semantic search
    - Semantic ranking for improved relevance
    """
    index = SearchIndex(
        name=INDEX_NAME,
        fields=[
            # Key field
            SearchField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
                sortable=True
            ),
            # Parent document reference
            SearchField(
                name="parent_id",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True
            ),
            # Document content chunk
            SearchField(
                name="chunk",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=False,
                sortable=False
            ),
            # Document title/filename
            SearchField(
                name="title",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True
            ),
            # Vector embedding field
            SearchField(
                name="text_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                stored=False,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name="vector-profile"
            ),
            # Metadata fields
            SearchField(
                name="metadata_storage_path",
                type=SearchFieldDataType.String,
                filterable=True
            ),
            SearchField(
                name="metadata_storage_name",
                type=SearchFieldDataType.String,
                filterable=True
            )
        ],
        vector_search=VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config",
                    vectorizer_name="openai-vectorizer"
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-config")
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="openai-vectorizer",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=AZURE_OPENAI_ENDPOINT,
                        deployment_name=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                        model_name=AZURE_OPENAI_EMBEDDING_MODEL
                    )
                )
            ]
        ),
        semantic_search=SemanticSearch(
            default_configuration_name="semantic-config",
            configurations=[
                SemanticConfiguration(
                    name="semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[
                            SemanticField(field_name="chunk")
                        ]
                    )
                )
            ]
        )
    )
    
    index_client.create_or_update_index(index)
    print(f"✓ Index '{INDEX_NAME}' created or updated successfully")


def create_blob_data_source(index_client: SearchIndexClient) -> None:
    """
    Create a data source connection to Azure Blob Storage using Entra ID.
    
    This connects the indexer to your blob container containing
    workforce documents (PDFs, Word docs, etc.)
    
    Uses managed identity authentication instead of connection strings.
    Requires: Azure AI Search managed identity must have 'Storage Blob Data Reader' role.
    """
    from azure.search.documents.indexes.models import SearchIndexerDataIdentity
    
    data_source_name = f"{INDEX_NAME}-datasource"
    
    data_source = SearchIndexerDataSourceConnection(
        name=data_source_name,
        type="azureblob",
        connection_string=f"ResourceId={BLOB_STORAGE_RESOURCE_ID};",
        container=SearchIndexerDataContainer(
            name=BLOB_CONTAINER_NAME
        ),
        identity=SearchIndexerDataIdentity(type="SystemAssigned")
    )
    
    index_client.create_or_update_data_source_connection(data_source)
    print(f"✓ Data source '{data_source_name}' created or updated successfully (using Entra ID)")
    return data_source_name


def create_skillset(index_client: SearchIndexClient) -> str:
    """
    Create a skillset for document processing.
    
    The skillset:
    1. Splits documents into chunks
    2. Generates embeddings for each chunk using Azure OpenAI
    """
    skillset_name = f"{INDEX_NAME}-skillset"
    
    skillset = SearchIndexerSkillset(
        name=skillset_name,
        description="Skillset for chunking and embedding workforce documents",
        skills=[
            # Split documents into chunks
            SplitSkill(
                name="split-skill",
                description="Split documents into chunks",
                text_split_mode="pages",
                maximum_page_length=2000,
                page_overlap_length=500,
                inputs=[
                    InputFieldMappingEntry(name="text", source="/document/content")
                ],
                outputs=[
                    OutputFieldMappingEntry(name="textItems", target_name="pages")
                ]
            ),
            # Generate embeddings for chunks
            AzureOpenAIEmbeddingSkill(
                name="embedding-skill",
                description="Generate embeddings using Azure OpenAI",
                resource_url=AZURE_OPENAI_ENDPOINT,
                deployment_name=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                model_name=AZURE_OPENAI_EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                inputs=[
                    InputFieldMappingEntry(name="text", source="/document/pages/*")
                ],
                outputs=[
                    OutputFieldMappingEntry(name="embedding", target_name="text_vector")
                ],
                context="/document/pages/*"
            )
        ],
        index_projection=SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=INDEX_NAME,
                    parent_key_field_name="parent_id",
                    source_context="/document/pages/*",
                    mappings=[
                        InputFieldMappingEntry(name="chunk", source="/document/pages/*"),
                        InputFieldMappingEntry(name="text_vector", source="/document/pages/*/text_vector"),
                        InputFieldMappingEntry(name="title", source="/document/metadata_storage_name")
                    ]
                )
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode="generatedKeyAsId"
            )
        )
    )
    
    index_client.create_or_update_skillset(skillset)
    print(f"✓ Skillset '{skillset_name}' created or updated successfully")
    return skillset_name


def create_indexer(index_client: SearchIndexClient, data_source_name: str, skillset_name: str) -> None:
    """
    Create an indexer to process documents from Blob Storage.
    
    The indexer:
    1. Reads documents from the blob container
    2. Applies the skillset (chunking + embedding)
    3. Stores results in the search index
    """
    indexer_name = f"{INDEX_NAME}-indexer"
    
    indexer = SearchIndexer(
        name=indexer_name,
        description="Indexer for workforce documents",
        data_source_name=data_source_name,
        target_index_name=INDEX_NAME,
        skillset_name=skillset_name,
        parameters=IndexingParameters(
            configuration=IndexingParametersConfiguration(
                parsing_mode="default",
                data_to_extract="contentAndMetadata"
            )
        ),
        field_mappings=[
            # Map blob metadata to index fields
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "metadata_storage_path"},
            {"sourceFieldName": "metadata_storage_name", "targetFieldName": "metadata_storage_name"}
        ]
    )
    
    index_client.create_or_update_indexer(indexer)
    print(f"✓ Indexer '{indexer_name}' created or updated successfully")
    print(f"  → Run indexer to start processing: az search indexer run --name {indexer_name} --service-name <search-service>")


def create_knowledge_source(index_client: SearchIndexClient) -> None:
    """
    Create a knowledge source pointing to the search index.
    
    The knowledge source is used by the knowledge base to perform
    agentic retrieval queries.
    """
    knowledge_source = SearchIndexKnowledgeSource(
        name=KNOWLEDGE_SOURCE_NAME,
        description="Knowledge source for workforce data (skills, certifications, availability)",
        search_index_parameters=SearchIndexKnowledgeSourceParameters(
            search_index_name=INDEX_NAME,
            source_data_fields=[
                SearchIndexFieldReference(name="chunk_id"),
                SearchIndexFieldReference(name="title"),
                SearchIndexFieldReference(name="metadata_storage_name")
            ]
        )
    )
    
    index_client.create_or_update_knowledge_source(knowledge_source=knowledge_source)
    print(f"✓ Knowledge source '{KNOWLEDGE_SOURCE_NAME}' created or updated successfully")


def create_knowledge_base(index_client: SearchIndexClient) -> str:
    """
    Create a knowledge base that wraps the knowledge source.
    
    The knowledge base provides:
    - Intelligent query planning with LLM
    - Multi-query synthesis
    - MCP endpoint for agent integration
    
    Returns the MCP endpoint URL for use with Foundry agents.
    """
    knowledge_base = KnowledgeBase(
        name=KNOWLEDGE_BASE_NAME,
        knowledge_sources=[
            KnowledgeSourceReference(name=KNOWLEDGE_SOURCE_NAME)
        ],
        output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
        retrieval_reasoning_effort=KnowledgeRetrievalMinimalReasoningEffort()
    )
    
    index_client.create_or_update_knowledge_base(knowledge_base=knowledge_base)
    print(f"✓ Knowledge base '{KNOWLEDGE_BASE_NAME}' created or updated successfully")
    
    # Generate MCP endpoint URL
    mcp_endpoint = f"{AZURE_SEARCH_ENDPOINT}/knowledgebases/{KNOWLEDGE_BASE_NAME}/mcp?api-version=2025-11-01-Preview"
    print(f"\n📡 MCP Endpoint URL:")
    print(f"   {mcp_endpoint}")
    print(f"\n   Use this URL in FOUNDRY_KNOWLEDGE_BASE_MCP_URL environment variable")
    
    return mcp_endpoint


def run_indexer(index_client: SearchIndexClient) -> None:
    """
    Optionally run the indexer to start processing documents.
    """
    indexer_name = f"{INDEX_NAME}-indexer"
    
    try:
        index_client.run_indexer(indexer_name)
        print(f"\n🚀 Indexer '{indexer_name}' started. Check status with:")
        print(f"   az search indexer status --name {indexer_name} --service-name <search-service>")
    except Exception as e:
        print(f"\n⚠️  Could not start indexer: {e}")
        print(f"   You can manually run: az search indexer run --name {indexer_name} --service-name <search-service>")


def main():
    """
    Main entry point - creates all required resources for a Knowledge Base
    backed by Azure Blob Storage.
    """
    print("=" * 60)
    print("Creating Azure AI Search Knowledge Base from Blob Storage")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Search Endpoint: {AZURE_SEARCH_ENDPOINT}")
    print(f"  Index Name: {INDEX_NAME}")
    print(f"  Blob Container: {BLOB_CONTAINER_NAME}")
    print(f"  Knowledge Base: {KNOWLEDGE_BASE_NAME}")
    print()
    
    # Initialize the search index client
    index_client = SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=credential
    )
    
    # Step 1: Create search index
    print("\n[1/6] Creating search index...")
    create_search_index(index_client)
    
    # Step 2: Create blob data source
    print("\n[2/6] Creating blob data source...")
    data_source_name = create_blob_data_source(index_client)
    
    # Step 3: Create skillset
    print("\n[3/6] Creating skillset...")
    skillset_name = create_skillset(index_client)
    
    # Step 4: Create indexer
    print("\n[4/6] Creating indexer...")
    create_indexer(index_client, data_source_name, skillset_name)
    
    # Step 5: Create knowledge source
    print("\n[5/6] Creating knowledge source...")
    create_knowledge_source(index_client)
    
    # Step 6: Create knowledge base
    print("\n[6/6] Creating knowledge base...")
    mcp_endpoint = create_knowledge_base(index_client)
    
    # Optional: Run the indexer
    print("\n" + "-" * 60)
    run_indexer_prompt = input("Do you want to run the indexer now? (y/n): ").strip().lower()
    if run_indexer_prompt == 'y':
        run_indexer(index_client)
    
    print("\n" + "=" * 60)
    print("✅ Knowledge Base setup complete!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"1. Upload workforce documents to blob container: {BLOB_CONTAINER_NAME}")
    print(f"2. Run the indexer to process documents")
    print(f"3. Update .env with:")
    print(f"   FOUNDRY_KNOWLEDGE_BASE_MCP_URL={mcp_endpoint}")
    print(f"4. Create MCP connection: python createFoundryIQMCPConnection.py")
    print(f"5. Create Prompt Agent: python createPromptAgentWithFoundryIQ.py")


if __name__ == "__main__":
    main()
