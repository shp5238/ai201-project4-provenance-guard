const analyzeButton = document.getElementById("analyzeButton");
const appealButton = document.getElementById("appealButton");
const logButton = document.getElementById("logButton");
const textInput = document.getElementById("textInput");
const appealInput = document.getElementById("appealInput");
const results = document.getElementById("results");

const creatorId = "frontend-user";
let latestContentId = null;

analyzeButton.addEventListener("click", analyzeText);
appealButton.addEventListener("click", submitAppeal);
logButton.addEventListener("click", viewLog);

async function analyzeText() {

    const text = textInput.value;
    results.textContent = "Analyzing...";

    try {
        const response = await fetch("/submit", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                text: text,
                creator_id: creatorId

            })

        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "The server could not analyze this text.");
        }

        latestContentId = result.content_id || null;
        results.textContent = JSON.stringify(result, null, 4);
    } catch (error) {
        results.textContent = `Error: ${error.message}`;
    }
}

async function submitAppeal() {

    const reasoning = appealInput.value.trim();

    if (!latestContentId) {
        results.textContent = "Error: Analyze text before submitting an appeal.";
        return;
    }

    if (!reasoning) {
        results.textContent = "Error: Enter an appeal reason before submitting.";
        return;
    }

    results.textContent = "Submitting appeal...";

    try {
        const response = await fetch("/appeal", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                content_id: latestContentId,
                creator_id: creatorId,
                creator_reasoning: reasoning

            })

        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "The server could not submit this appeal.");
        }

        results.textContent = JSON.stringify(result, null, 4);
    } catch (error) {
        results.textContent = `Error: ${error.message}`;
    }
}

async function viewLog() {

    results.textContent = "Loading audit log...";

    try {
        const response = await fetch("/log");
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "The server could not load the audit log.");
        }

        results.textContent = JSON.stringify(result, null, 4);
    } catch (error) {
        results.textContent = `Error: ${error.message}`;
    }
}
