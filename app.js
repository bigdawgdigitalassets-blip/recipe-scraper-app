// A public CORS proxy bridge to bypass data-center IP blocks
const CORS_PROXY = "https://herokuapp.com";

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

    // Ensure the user-pasted string has a proper HTTP protocol prefix
    if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
        targetUrl = "https://" + targetUrl;
    }

    extractBtn.textContent = "Scraping...";
    extractBtn.disabled = true;
    outputDiv.style.display = "none";

    try {
        // Route request through the proxy bridge to bypass the 403 block
        const proxyUrl = CORS_PROXY + targetUrl;
        console.log("Fetching webpage via proxy bridge:", proxyUrl);

        const response = await fetch(proxyUrl, {
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        });

        if (!response.ok) {
            if (response.status === 403) {
                throw new Error("CORS Proxy requires temporary activation. Please visit https://herokuapp.com and click 'Opt In'.");
            }
            throw new Error(`Proxy gateway responded with status: ${response.status}`);
        }

        const htmlContent = await response.text();
        
        // Locate and extract the LD+JSON schema block natively in-browser
        const regex = /<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
        let match;
        let recipeData = null;

        while ((match = regex.exec(htmlContent)) !== null) {
            try {
                const parsed = JSON.parse(match[1].trim());
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
                // Ignore invalid or unparseable JSON-LD blocks
            }
        }

        if (!recipeData) {
            throw new Error("Could not locate a clean recipe metadata template on this page.");
        }

        // Map values into state memory
        currentIngredientsArray = recipeData.recipeIngredient || [];
        document.getElementById("scale-select").value = "1";
        document.getElementById("recipe-title").textContent = recipeData.name || "Scraped Recipe";
        
        // Execute initial text render
        renderScaledIngredients(1); 
        outputDiv.style.display = "block";

    } catch (error) {
        console.error("Scraping Breakdown:", error);
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