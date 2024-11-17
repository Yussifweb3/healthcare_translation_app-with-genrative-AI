let audioChunks = [];
let mediaRecorder;

// Fetch definitions for medical terms
async function fetchDefinitions(terms) {
    const response = await fetch("/define", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ terms })
    });
    const data = await response.json();
    return data.definitions;
}

// Highlight medical terms and attach explanations
function highlightMedicalTerms(text, terms) {
    const wordList = text.split(/\s+/);

    // Fetch definitions and highlight terms
    fetchDefinitions(terms).then(definitions => {
        const highlightedText = wordList.map(word => {
            if (definitions[word]) {
                return `<span class="medical-term" onclick="alert('${word}: ${definitions[word]}')">${word}</span>`;
            }
            return word;
        }).join(" ");

        document.getElementById("outputText").innerHTML = highlightedText;
    });
}

// Start audio recording
document.getElementById("startRecording").addEventListener("click", async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
        const reader = new FileReader();
        reader.onload = async () => {
            const base64Audio = reader.result.split(",")[1];
            const response = await fetch("/transcribe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ audio: base64Audio })
            });
            const data = await response.json();
            document.getElementById("inputText").value = data.transcription || data.error;
        };
        reader.readAsDataURL(audioBlob);
    };

    mediaRecorder.start();
    alert("Recording started...");
});

// Stop audio recording
document.getElementById("stopRecording").addEventListener("click", () => {
    if (mediaRecorder) {
        mediaRecorder.stop();
        alert("Recording stopped!");
    }
});

// Translate text based on user-selected languages
document.getElementById("translateButton").addEventListener("click", async () => {
    const inputText = document.getElementById("inputText").value;
    const sourceLang = document.getElementById("sourceLang").value;
    const targetLang = document.getElementById("targetLang").value;

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

    // Highlight medical terms in the translated text
    const terms = inputText.split(/\s+/); // Split input text to find terms
    highlightMedicalTerms(data.translation, terms);
});
