// Ensure the string ends exactly with /?url=
const CORS_PROXY = "https://corsproxy.io";

let currentIngredientsArray = [];

document.getElementById("extract-btn").addEventListener("click", async () => {
    const urlInput = document.getElementById("recipe-url");
    const extractBtn = document.getElementById("extract-btn");
    const outputDiv = document.getElementById("recipe-output");
    let targetUrl = urlInput.value.trim();

    if (!targetUrl) {
        alert("Please enter a valid recipe URL first!");
        return;
    }

    if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
        targetUrl = "https://" + targetUrl;
    }

    extractBtn.textContent = "Scraping...";
    extractBtn.disabled = true;
    outputDiv.style.display = "none";

    try {
        // Encode the URL cleanly to make sure formatting marks don't break the proxy path
        const proxyUrl = CORS_PROXY + encodeURIComponent(targetUrl);
        console.log("Routing traffic via corsproxy engine:", proxyUrl);

        const response = await fetch(proxyUrl);

        if (!response.ok) {
            throw new Error(`Proxy network returned validation error state: ${response.status}`);
        }

        const htmlContent = await response.text();
        
        // Target and extract the structured schema scripts inside the HTML shell
        const regex = /<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
        let match;
        let recipeData = null;

        while ((match = regex.exec(htmlContent)) !== null) {
            try {
                const parsed = JSON.parse(match.trim());
                const items = Array.isArray(parsed) ? parsed : [parsed];
                for (const item of items) {
                    if (item["@type"] === "Recipe" || (Array.isArray(item["@type"]) && item["@type"].includes("Recipe"))) {
                        recipeData = item;
                        break;
                    } else if (item["@graph"] && Array.isArray(item["@graph"])) {
                        for (const subItem of item["@graph"]) {
                            if (subItem["@type"] === "Recipe") {
                                recipeData = subItem;
                                break;
                            }
                        }
                    }
                }
                if (recipeData) break;
            } catch (e) {
                // Skip mismatched structural scripts
            }
        }

        if (!recipeData) {
            throw new Error("Could not parse structured recipe data from this webpage layout.");
        }

        currentIngredientsArray = recipeData.recipeIngredient || [];
        document.getElementById("scale-select").value = "1";
        document.getElementById("recipe-title").textContent = recipeData.name || "Scraped Recipe";
        
        renderScaledIngredients(1); 
        outputDiv.style.display = "block";

    } catch (error) {
        console.error("Scraper Engine Breakdown Log:", error);
        alert(`Extraction Failed: ${error.message}`);
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
            const originalNumStr = match;
            let decimalValue = 0;

            if (originalNumStr.includes(' ') && originalNumStr.includes('/')) {
                const parts = originalNumStr.split(/\s+/);
                const whole = parseInt(parts, 10);
                const fracParts = parts.split('/');
                decimalValue = whole + (parseInt(fracParts, 10) / parseInt(fracParts, 10));
            } else if (originalNumStr.includes('/')) {
                const fracParts = originalNumStr.split('/');
                decimalValue = parseInt(fracParts, 10) / parseInt(fracParts, 10);
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