const analyzeButton = document.getElementById("analyzeButton");
const textInput = document.getElementById("textInput");
const results = document.getElementById("results");

analyzeButton.addEventListener("click", analyzeText);

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
                creator_id: "frontend-user"

            })

        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || "The server could not analyze this text.");
        }

        results.textContent = JSON.stringify(result, null, 4);
    } catch (error) {
        results.textContent = `Error: ${error.message}`;
    }
}
