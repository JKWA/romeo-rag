import time
import httpx
import chromadb
import argparse
import asyncio
from urllib.parse import urljoin
from logger import setup_logger
from dotenv import load_dotenv
import os

load_dotenv()
logger = setup_logger(__name__)


base_ai_url = os.getenv("AI_BASEPATH")
chromabasepath = os.getenv("CHROMA_BASEPATH")
collectionname = os.getenv("CHROMA_COLLECTION_NAME")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
embedmodel = os.getenv("EMBED_MODEL")
textextractbasepath = os.getenv("TEXT_EXTRACT_BASEPATH")

headers = {"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": client_secret}


async def reset_data(sentences_per_chunk, overlap):
    """
    Process files and perform necessary operations.

    Args:
        sentences_per_chunk (int): Number of sentences per chunk.
        overlap (int): Number of overlapping sentences between chunks.

    Returns:
        None
    """
    chroma = chromadb.HttpClient(host=chromabasepath)
    if any(
        collection.name == collectionname for collection in chroma.list_collections()
    ):
        logger.info(f"Deleting: {collectionname}")
        chroma.delete_collection(collectionname)

        logger.info(f"Resetting: {collectionname}")
    collection = chroma.get_or_create_collection(
        name=collectionname, metadata={"hnsw:space": "cosine"}
    )
    logger.info(f'Collection "{collectionname}" ready for use.')
    logger.info("Processing files...")
    await _process_url_contents(collection, sentences_per_chunk, overlap)


async def _process_url_contents(collection, sentences_per_chunk, overlap):
    """Process each URL in the file, fetch its content,
    and add extracted chunks to the collection."""
    starttime = time.time()

    with open("sourcedocs.txt") as f:
        lines = f.readlines()

    for url in lines:
        url = url.strip()
        text = await _fetch_content_from_url(url)
        if text is None:
            logger.info(f"Failed to fetch content from URL: {url}")
            continue

        chunks = await _extract_chunks_from_service(
            text, sentences_per_chunk=sentences_per_chunk, overlap=overlap
        )
        for index, chunk in enumerate(chunks):
            embed = await _get_embedding(chunk, embedmodel)
            if embed is None:
                logger.info(
                    f"Failed to get embedding for chunk {index+1} of URL: {url}"
                )
                continue

            try:
                collection.add(
                    [url + str(index)],
                    [embed],
                    documents=[chunk],
                    metadatas=[{"source": url}],
                )
                print(".", end="", flush=True)
            except Exception as e:
                logger.error(f"Error adding chunk {index+1} to collection: {str(e)}")

    logger.info(
        f"\n\n--- Process completed in {time.time() - starttime:.2f} seconds ---"
    )
    return "URL processing completed successfully"


async def _fetch_content_from_url(url):
    """
    Fetches content from the specified URL asynchronously.

    Args:
        url (str): The URL to fetch content from.

    Returns:
        str: The content fetched from the URL, or None if an error occurred.
    """
    logger.info(f"\n\nDownloading content from URL: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            logger.info("Content downloaded successfully.")
            return response.text
    except Exception as e:
        logger.error(f"Error fetching URL content from {url}: {str(e)}")
    return None


async def _extract_chunks_from_service(file_content, sentences_per_chunk, overlap):
    """
    Extracts chunks from a given file content using a service.

    Args:
        file_content (str): The content of the file to extract chunks from.
        sentences_per_chunk (int): The number of sentences per chunk.
        overlap (int): The overlap between chunks.

    Returns:
        list: A list of extracted chunks.

    Raises:
        Exception: If there is an error extracting chunks.

    """
    logger.info("Starting chunking process...")
    base_url = urljoin(textextractbasepath, "extract-chunks/")
    params = {"sentences_per_chunk": sentences_per_chunk, "overlap": overlap}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                base_url,
                params=params,
                files={"file": ("content.html", file_content, "text/html")},
            )
            response.raise_for_status()
            chunks = response.json()["chunks"]
            logger.info(f"\nChunking complete. \nLoading {len(chunks)}.")
            return chunks
    except Exception as e:
        logger.error(f"Error extracting chunks: {str(e)}")
    return []


async def _get_embedding(text, model):
    """
    Get the embedding for the given text using the specified model.

    Args:
        text (str): The text to get the embedding for.
        model (str): The name of the model to use for embedding.

    Returns:
        str: The embedding of the text.

    Raises:
        Exception: If there is an error getting the embedding.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                urljoin(base_ai_url, "embeddings"),
                json={"model": model, "prompt": text},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["embedding"]
    except Exception as e:
        logger.error(f"Error getting embedding: {str(e)}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Reset data utility.")
    parser.add_argument(
        "sentences_per_chunk", type=int, help="Number of sentences per chunk"
    )
    parser.add_argument("overlap", type=int, help="Overlap between chunks")
    args = parser.parse_args()

    # Run the async reset_data function
    asyncio.run(reset_data(args.sentences_per_chunk, args.overlap))


if __name__ == "__main__":
    main()
