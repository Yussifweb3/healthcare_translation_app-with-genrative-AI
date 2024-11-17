from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai
import base64
import tempfile
import os
import ffmpeg
import imageio_ffmpeg as imageio_ffmpeg

# Initialize Flask App
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# OpenAI API Key
openai.api_key = "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"


# In-memory cache for term definitions
cache = {}

# Helper Function: Convert Audio to 16-bit PCM WAV
def process_audio(input_audio_path, output_audio_path):
    """
    Converts an input audio file to a 16-bit PCM WAV format using FFmpeg.
    """
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()  # Fetch FFmpeg binary from imageio_ffmpeg
        (
            ffmpeg
            .input(input_audio_path)
            .output(
                output_audio_path,
                format="wav",
                acodec="pcm_s16le",
                ar="16000"
            )
            .run(cmd=ffmpeg_path, overwrite_output=True)
        )
        return output_audio_path
    except ffmpeg.Error as e:
        raise Exception(f"FFmpeg error: {e.stderr.decode()}") from e

# Helper Function: Clean Up Temporary Files
def cleanup_temp_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

# Route: Home Page
@app.route('/')
def index():
    return render_template('index.html')

# Route: Transcribe Audio
@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    data = request.json
    audio_content = data.get("audio")

    if not audio_content:
        return jsonify({"error": "No audio provided"}), 400

    try:
        # Decode base64 audio and save as a temporary file
        raw_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        with open(raw_audio_path, "wb") as f:
            f.write(base64.b64decode(audio_content))

        # Convert audio to compatible format for Whisper
        processed_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        processed_audio_path = process_audio(raw_audio_path, processed_audio_path)

        # Perform transcription using OpenAI Whisper
        with open(processed_audio_path, "rb") as audio_file:
            response = openai.Audio.transcribe(
                file=audio_file,
                model="whisper-1"
            )

        # Clean up temporary files
        cleanup_temp_file(raw_audio_path)
        cleanup_temp_file(processed_audio_path)

        return jsonify({"transcription": response.get("text", "")})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Translate Text
@app.route('/translate', methods=['POST'])
def translate_text():
    data = request.json
    text = data.get("text")
    source_lang = data.get("source_lang", "English")
    target_lang = data.get("target_lang", "Spanish")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful translator."},
                {"role": "user", "content": f"Translate the following text from {source_lang} to {target_lang}: {text}"}
            ],
            max_tokens=200
        )
        translated_text = response['choices'][0]['message']['content'].strip()
        return jsonify({"translation": translated_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Define Medical Terms
@app.route('/define', methods=['POST'])
def define_terms():
    data = request.json
    terms = data.get("terms", [])

    if not terms:
        return jsonify({"error": "No terms provided"}), 400

    cached_results = {}
    terms_to_query = []

    # Check dictionary cache
    for term in terms:
        if term in cache:
            cached_results[term] = cache[term]
        else:
            terms_to_query.append(term)

    # Query OpenAI for uncached terms
    if terms_to_query:
        try:
            query = ", ".join(terms_to_query)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical assistant pic only words which are medically related in any language and explain only them dont explain all the other words provided. Like Fever in Spanish is Fiebre, so i want you to explain it in very few words"},
                    {"role": "user", "content": f"Identify and explain these terms: {query}"}
                ],
                max_tokens=500
            )
            explanations = response['choices'][0]['message']['content'].strip()

            # Parse and cache results
            for term, explanation in zip(terms_to_query, explanations.split("\n")):
                cache[term] = explanation
                cached_results[term] = explanation

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"definitions": cached_results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Get the port from the environment or default to 5000
    app.run(host="0.0.0.0", port=port, debug=True)
