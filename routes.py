from flask import Response, render_template, request, jsonify, stream_with_context
from services.search import get_streamed_results
from services.settings import reset_data
import asyncio
from .app import app


def run_async_process(sentences_per_chunk, overlap):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(reset_data(sentences_per_chunk, overlap))
    loop.close()
    return result


@app.route("/")
def index():
    return render_template("search.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/stream")
def stream():
    query = request.args.get("query")
    n_results = request.args.get("n_results", type=int, default=10)

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async_gen = get_streamed_results(query, n_results)
        try:
            while True:
                try:
                    result = loop.run_until_complete(async_gen.__anext__())
                    yield f"data: {result}\n\n"
                except StopAsyncIteration:
                    break
                except Exception as e:
                    yield f"data: Error: {str(e)}\n\n"
        finally:
            loop.close()

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/reset-data", methods=["POST"])
def reset():
    data = request.get_json()
    sentences_per_chunk = int(data.get("sentences_per_chunk"))
    overlap = int(data.get("overlap"))

    result = run_async_process(sentences_per_chunk, overlap)

    return jsonify({"status": "success", "message": result})
