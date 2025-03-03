let mediaRecorder; // To manage the media recorder
let audioChunks = []; // To store audio data

// Fetch definitions for medical terms
async function fetchDefinitions(words, sourceLang, targetLang) {
    try {
        const response = await fetch("/define", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ terms: words, source_lang: sourceLang, target_lang: targetLang })
        });
        const data = await response.json();
        if (data.definitions) {
            return data.definitions;
        } else {
            console.error("Error fetching definitions:", data.error);
            return {};
        }
    } catch (error) {
        console.error("Error fetching definitions:", error);
        return {};
    }
}

// Display medical term definitions
function displayDefinitions(definitions) {
    const definitionArea = document.getElementById("definitionArea");
    definitionArea.innerHTML = ""; // Clear previous definitions

    for (const [term, { source, target }] of Object.entries(definitions)) {
        const defElement = document.createElement("p");
        defElement.innerHTML = `<strong>${term}:</strong>
                                <br> In Source Language: ${source}
                                <br> In Target Language: ${target}`;
        definitionArea.appendChild(defElement);
    }
}

// Translate text and display definitions
document.getElementById("translateButton").addEventListener("click", async () => {
    const inputText = document.getElementById("inputText").value;
    const sourceLang = document.getElementById("sourceLang").value;
    const targetLang = document.getElementById("targetLang").value;

    if (!inputText.trim()) {
        alert("Please enter text to translate!");
        return;
    }

    try {
        // Extract words from input text
        const words = inputText.split(/\s+/);

        // Fetch medical term definitions
        const definitions = await fetchDefinitions(words, sourceLang, targetLang);

        // Display definitions below the translation
        displayDefinitions(definitions);

        // Translate the input text
        const response = await fetch("/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: inputText,
                source_lang: sourceLang,
                target_lang: targetLang
            })
        });

        const data = await response.json();
        if (data.translation) {
            document.getElementById("outputText").innerHTML = data.translation;
            // Show the "Speak" button
            document.getElementById("speakButton").style.display = "block";
        } else {
            console.error("Error during translation:", data.error);
            alert("Translation failed. Please try again.");
        }
    } catch (error) {
        console.error("Error during translation process:", error);
        alert("An error occurred. Please try again.");
    }
});

// Start audio recording
document.getElementById("startRecording").addEventListener("click", async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        audioChunks = []; // Reset the audio chunks array
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.start();
        alert("Recording started...");

        // Enable the "Stop Recording" button
        document.getElementById("stopRecording").disabled = false;
        document.getElementById("startRecording").disabled = true;
    } catch (error) {
        console.error("Error accessing microphone:", error);
        alert("Unable to access microphone. Please check your permissions.");
    }
});

// Stop audio recording and play back the recorded audio
document.getElementById("stopRecording").addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        alert("Recording stopped!");

        // Disable the "Stop Recording" button
        document.getElementById("stopRecording").disabled = true;
        document.getElementById("startRecording").disabled = false;
    } else {
        alert("No active recording to stop!");
    }

    mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });

        // Play back the recorded audio
        const audioPlayer = document.getElementById("audioPlayer");
        audioPlayer.src = URL.createObjectURL(audioBlob);
        audioPlayer.style.display = "block";
        audioPlayer.play();

        // Convert the audio to base64 for transcription
        const reader = new FileReader();
        reader.onload = async () => {
            const base64Audio = reader.result.split(",")[1];
            try {
                const response = await fetch("/transcribe", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ audio: base64Audio })
                });

                const data = await response.json();
                if (data.transcription) {
                    document.getElementById("inputText").value = data.transcription;
                } else {
                    console.error("Error during transcription:", data.error);
                    alert("Transcription failed. Please try again.");
                }
            } catch (error) {
                console.error("Error during transcription request:", error);
                alert("An error occurred during transcription. Please try again.");
            }
        };
        reader.readAsDataURL(audioBlob);
    };
});

// Speak the translated text
document.getElementById("speakButton").addEventListener("click", () => {
    const translatedText = document.getElementById("outputText").innerText;
    if (translatedText) {
        const utterance = new SpeechSynthesisUtterance(translatedText);
        utterance.lang = document.getElementById("targetLang").value; // Set the language
        speechSynthesis.speak(utterance);
    } else {
        alert("No translated text to speak!");
    }
});
