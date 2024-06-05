
# Romeo RAG

Romeo RAG is a retrieval-augmented generation system that uses advanced search techniques to generate relevant responses. This application serves as a backend, responding to specific queries with relevant information.

## Requirements

- Python 3.x
- Flask
- Any other dependencies listed in `requirements.txt`

## Setup

To set up the project environment and install the required dependencies:

```bash
make setup
```

## Running the Application

### Locally

To run the application locally:

```bash
make run-local
```

## Interacting with the Application

### Reset Data

To reset the data configuration for chunk processing:

```bash
make reset-data
```

or with parameters

```bash
make reset-data SENTENCES_PER_CHUNK=20 OVERLAP=5
```

### Sending a Test Query

You can send a test query to the application using:

```bash
make test-query
```

or with parameters

```bash
make test-query QUERY="Did Romeo die?" N_RESULTS=15
```

### Change sources

You can change the sources by updating sourcedocs.txt
