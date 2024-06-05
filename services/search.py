import httpx
import json
import chromadb
import argparse
import asyncio
from urllib.parse import urljoin
from logger import setup_logger
from dotenv import load_dotenv
import os

load_dotenv()
logger = setup_logger(__name__)

RELEVANCE_THRESHOLD = 1

base_ai_url = os.getenv("AI_BASEPATH")
chromabasepath = os.getenv("CHROMA_BASEPATH")
collectionname = os.getenv("CHROMA_COLLECTION_NAME")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
embedmodel = os.getenv("EMBED_MODEL")
mainmodel = os.getenv("MAIN_MODEL")
textextractbasepath = os.getenv("TEXT_EXTRACT_BASEPATH")

headers = {"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": client_secret}


async def get_streamed_results(query, n_results):
    """
    Retrieves search results based on the given query.

    Args:
        query (str): The search query.
        n_results (int): The number of search results to retrieve.

    Yields:
        str: The search results as a string.

    Returns:
        None
    """
    chroma = chromadb.HttpClient(host=chromabasepath)
    collection = chroma.get_or_create_collection(collectionname)

    logger.info(f"get embeds from:{query} using:{embedmodel}")
    query_embedding = await _get_embedding(query, embedmodel)

    if query_embedding is None:
        yield "Failed to get embedding for query."
        return

    docs = await _fetch_relevant_documents(collection, query_embedding, n_results)

    if docs is None:
        yield "No suitable documents found."
        return

    model_query = _construct_query(query, docs)
    logger.info(f"query{model_query}")

    async for response in _generate_responses(model_query):
        yield response


async def _get_embedding(text, model):
    """
    Get the embedding for the given text using the specified model.

    Args:
        text (str): The text to get the embedding for.
        model (str): The name of the model to use for embedding.

    Returns:
        str: The embedding of the text as a string.

    Raises:
        httpx.HTTPStatusError: If an HTTP error occurs during the request.
        httpx.ConnectError: If a connection error occurs.
        Exception: If any other error occurs.

    """
    embed_url = urljoin(base_ai_url, "embeddings")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                embed_url, json={"model": model, "prompt": text}, headers=headers
            )
            response.raise_for_status()
            return response.json()["embedding"]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Ollama: HTTP error occurred: {e.response.status_code} - {e.response.text}"
        )
    except httpx.ConnectError as e:
        logger.error(f"Ollama: Connection error occurred: {str(e)}")
    except Exception as e:
        logger.error(f"Ollama: Error getting embedding from {embed_url}: {str(e)}")
    return None


async def _fetch_relevant_documents(collection, query_embedding, n_results):
    """
    Fetches relevant documents from a collection based on a query embedding.

    Args:
        collection: The collection to query.
        query_embedding: The query embedding to use for retrieval.
        n_results: The number of results to retrieve.

    Returns:
        A string containing the relevant documents joined by two newlines,
        or None if no relevant documents are found.

    Raises:
        Exception: If there is an error fetching the documents.
    """
    try:
        results = collection.query(
            query_embeddings=[query_embedding], n_results=n_results
        )
        if results["documents"]:
            relevant_docs = [
                doc
                for doc, dist in zip(results["documents"][0], results["distances"][0])
                if dist < RELEVANCE_THRESHOLD
            ]
            if not relevant_docs:
                return None

            return "\n\n".join(relevant_docs)
        else:
            return None
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return None


def _construct_query(query, docs):
    """
    Constructs a model query by combining the given query and document information.

    Args:
        query (str): The original query.
        docs (str): The document information.

    Returns:
        str: The constructed model query.
    """
    model_query = (
        f"{query} - Give a short answer to that question only using the following "
        "information as a resource. "
        "Use your own words. Do not tell me about the text. "
        f": {docs}"
    )
    return model_query


async def _generate_responses(model_query):
    """
    Generates responses by making a POST request to the AI model API.

    Args:
        model_query (str): The query to be used as the prompt for the AI model.

    Yields:
        str: The generated response from the AI model.

    Raises:
        httpx.HTTPStatusError: If an HTTP error occurs during the request.
        httpx.ConnectError: If a connection error occurs.
        Exception: If any other unexpected error occurs.
    """
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                urljoin(base_ai_url, "generate"),
                json={"model": mainmodel, "prompt": model_query},
                headers=headers,
            ) as response:
                response.raise_for_status()
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    try:
                        while buffer:
                            pos = buffer.find("}\n{") + 1
                            if pos == 0:
                                break
                            json_chunk = json.loads(buffer[:pos])
                            if "response" in json_chunk:
                                yield json_chunk["response"]
                            buffer = buffer[pos:]
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        continue

                if buffer:
                    try:
                        json_chunk = json.loads(buffer)
                        if "response" in json_chunk:
                            yield json_chunk["response"]
                    except json.JSONDecodeError as e:
                        logger.error(f"Final buffer JSON decode error: {e}")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        yield f"Generate: HTTP error: {e.response.status_code} - {e.response.text}"
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {e}")
        yield "Generate: Connection error occurred"
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        yield f"Generate: Unexpected error occurred: {e}"


async def main():
    parser = argparse.ArgumentParser(description="Test query utility.")
    parser.add_argument("query", type=str, help="Query to search for")
    parser.add_argument("n_results", type=int, help="Number of results to retrieve")
    args = parser.parse_args()

    # Create an async loop to handle the async generator
    async for result in get_streamed_results(args.query, args.n_results):
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
