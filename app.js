// !! REPLACE THIS URL WITH YOUR LIVE CLOUDFLARE WORKER URL LATER !!
const WORKER_API_URL = "https://recipe-scraper-backend.bigdawgdigitalasstes.workers.dev";

document.getElementById("extract-btn").addEventListener("click", async () => {
    const urlInput = document.getElementById("recipe-url");
    const extractBtn = document.getElementById("extract-btn");
    const outputDiv = document.getElementById("recipe-output");
    const targetUrl = urlInput.value.trim();

    if (!targetUrl) {
        alert("Please enter a valid recipe URL first!");
        return;
    }

    // Update UI state
    extractBtn.textContent = "Scraping...";
    extractBtn.disabled = true;
    outputDiv.style.display = "none";

    try {
        const response = await fetch(WORKER_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ recipeUrl: targetUrl })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "An error occurred while fetching the recipe.");
        }

        // Display the scraped results onto the interface
        outputDiv.innerHTML = `
            <h3>${data.title}</h3>
            <strong>Ingredients:</strong>
            <ul>${data.ingredients.map(ing => `<li>${ing}</li>`).join('')}</ul>
        `;
        outputDiv.style.display = "block";

    } catch (error) {
        alert(`Extraction Failed: ${error.message}`);
    } finally {
        extractBtn.textContent = "Extract recipe";
        extractBtn.disabled = false;
    }
});