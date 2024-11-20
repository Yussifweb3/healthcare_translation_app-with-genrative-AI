from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai
import os
import base64
import tempfile
import ffmpeg
import imageio_ffmpeg as imageio_ffmpeg

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Load OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Cache for storing medical term definitions
cache = {}

# Helper function: Convert audio to 16-bit PCM WAV
def process_audio(input_audio_path, output_audio_path):
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        (
            ffmpeg
            .input(input_audio_path)
            .output(output_audio_path, format="wav", acodec="pcm_s16le", ar="16000")
            .run(cmd=ffmpeg_path, overwrite_output=True)
        )
        return output_audio_path
    except ffmpeg.Error as e:
        raise Exception(f"FFmpeg error: {e.stderr.decode()}") from e

# Helper function: Clean up temporary files
def cleanup_temp_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

# Route: Home page
@app.route("/")
def index():
    return render_template("index.html")

# Route: Transcribe audio
@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    data = request.json
    audio_content = data.get("audio")

    if not audio_content:
        return jsonify({"error": "No audio provided"}), 400

    try:
        # Decode base64 audio and save it to a temporary file
        raw_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        with open(raw_audio_path, "wb") as f:
            f.write(base64.b64decode(audio_content))

        # Convert audio to compatible format
        processed_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        processed_audio_path = process_audio(raw_audio_path, processed_audio_path)

        # Perform transcription using OpenAI Whisper
        with open(processed_audio_path, "rb") as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file
            )

        # Clean up temporary files
        cleanup_temp_file(raw_audio_path)
        cleanup_temp_file(processed_audio_path)

        return jsonify({"transcription": response.get("text", "")})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Translate text
@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.json
    text = data.get("text", "")
    source_lang = data.get("source_lang", "English")
    target_lang = data.get("target_lang", "Spanish")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful translator."},
                {"role": "user", "content": f"Translate the following text from {source_lang} to {target_lang}: {text}"}
            ],
            max_tokens=500
        )
        translated_text = response["choices"][0]["message"]["content"].strip()
        return jsonify({"translation": translated_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Define medical terms
@app.route("/define", methods=["POST"])
def define_terms():
    data = request.json
    terms = data.get("terms", [])
    source_lang = data.get("source_lang", "English")
    target_lang = data.get("target_lang", "Spanish")

    if not terms:
        return jsonify({"error": "No terms provided"}), 400

    results = {}
    medical_terms_to_query = []

    # Step 1: Use OpenAI to filter only medical terms
    try:
        response_filter = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical assistant."},
                {
                    "role": "user",
                    "content": f"From the following list, identify only the medical terms and correct any typos if present: {', '.join(terms)}. Ignore non-medical words like 'and', 'the', etc."
                },
            ],
            max_tokens=200,
        )
        filtered_terms = response_filter["choices"][0]["message"]["content"].strip().split(", ")

    except Exception as e:
        return jsonify({"error": f"Error filtering medical terms: {str(e)}"}), 500

    # Step 2: Fetch definitions for filtered medical terms
    for term in filtered_terms:
        if term not in cache:
            medical_terms_to_query.append(term)

    if medical_terms_to_query:
        try:
            # Get definitions in source language
            query = ", ".join(medical_terms_to_query)
            response_source = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical assistant."},
                    {"role": "user", "content": f"Provide concise definitions for these medical terms in {source_lang}: {query}"}
                ],
                max_tokens=500
            )
            source_definitions = response_source["choices"][0]["message"]["content"].strip().split("\n")

            # Translate definitions into target language
            response_target = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful translator."},
                    {"role": "user", "content": f"Translate these definitions to {target_lang}: {source_definitions}"}
                ],
                max_tokens=500
            )
            target_definitions = response_target["choices"][0]["message"]["content"].strip().split("\n")

            # Cache results and prepare response
            for term, source_def, target_def in zip(
                medical_terms_to_query, source_definitions, target_definitions
            ):
                term = term.strip().lower()  # Ensure consistent term formatting
                cache[term] = {"source": source_def.strip(), "target": target_def.strip()}
                results[term] = {"source": source_def.strip(), "target": target_def.strip()}

        except Exception as e:
            return jsonify({"error": f"Error fetching definitions: {str(e)}"}), 500

    # Add cached results for terms already processed
    for term in filtered_terms:
        term = term.strip().lower()
        if term in cache:
            results[term] = cache[term]

    return jsonify({"definitions": results})


# Main entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
