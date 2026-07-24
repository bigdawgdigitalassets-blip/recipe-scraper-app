const WORKER_API_URL = "https://workers.dev";

let currentIngredientsArray = [];

document.getElementById("extract-btn").addEventListener("click", async () => {
    const urlInput = document.getElementById("recipe-url");
    const extractBtn = document.getElementById("extract-btn");
    const outputDiv = document.getElementById("recipe-output");
    const targetUrl = urlInput.value.trim();

    if (!targetUrl) {
        alert("Please enter a valid recipe URL first!");
        return;
    }

    extractBtn.textContent = "Scraping...";
    extractBtn.disabled = true;
    outputDiv.style.display = "none";

    try {
        console.log("Sending outbound fetch parameters to edge gateway:", WORKER_API_URL);
        
        // Explicitly format a bare payload object to pass safely through browser runtime checks
        const response = await fetch(WORKER_API_URL, {
            method: "POST",
            mode: "cors", // Explicitly instruct the browser to allow Cross-Origin Resource Sharing
            headers: { 
                "Content-Type": "text/plain" // Using text/plain avoids triggering aggressive preflight blocks
            },
            body: JSON.stringify({ recipeUrl: targetUrl })
        });

        console.log("Network status received back from edge:", response.status);
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || `Server responded with status ${response.status}`);

        currentIngredientsArray = data.ingredients;
        document.getElementById("scale-select").value = "1";
        document.getElementById("recipe-title").textContent = data.title;
        renderScaledIngredients(1); 
        
        outputDiv.style.display = "block";

    } catch (error) {
        console.error("Verbose Network Breakdown Log:", error);
        alert(`Extraction Failed: ${error.message}\n\nCheck your browser Console (F12) for detailed logs.`);
    } finally {
        extractBtn.textContent = "Extract recipe";
        extractBtn.disabled = false;
    }
});

document.getElementById("scale-select").addEventListener("change", (e) => {
    renderScaledIngredients(parseFloat(e.target.value));
});

function renderScaledIngredients(factor) {
    const listContainer = document.getElementById("ingredients-list");
    listContainer.innerHTML = "";

    currentIngredientsArray.forEach(ingredientStr => {
        let modifiedStr = ingredientStr;
        const numberRegex = /^(\d+\s+\d+\/\d+|\d+\/\d+|\d+\.\d+|\d+)/;
        const match = ingredientStr.match(numberRegex);

        if (match) {
            const originalNumStr = match[0];
            let decimalValue = 0;

            if (originalNumStr.includes(' ') && originalNumStr.includes('/')) {
                const parts = originalNumStr.split(/\s+/);
                const whole = parseInt(parts[0], 10);
                const fracParts = parts[1].split('/');
                decimalValue = whole + (parseInt(fracParts[0], 10) / parseInt(fracParts[1], 10));
            } else if (originalNumStr.includes('/')) {
                const fracParts = originalNumStr.split('/');
                decimalValue = parseInt(fracParts[0], 10) / parseInt(fracParts[1], 10);
            } else {
                decimalValue = parseFloat(originalNumStr);
            }

            const calculatedValue = (decimalValue * factor);
            const displayValue = Number(calculatedValue.toFixed(2)).toString();
            modifiedStr = ingredientStr.replace(originalNumStr, displayValue);
        }

        const cleanLiElement = document.createElement("li");
        cleanLiElement.textContent = modifiedStr;
        listContainer.appendChild(cleanLiElement);
    });
}