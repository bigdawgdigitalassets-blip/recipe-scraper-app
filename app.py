from flask import Flask, request, jsonify, render_template_string
import os

# New, safe import routing for recipe-scrapers library versions
try:
    from recipe_scrapers._factory import SchemaScraperFactory as scrape_me
except ImportError:
    try:
        from recipe_scrapers import scrape_me
    except ImportError:
        from recipe_scrapers import scraper as scrape_me
app = Flask(__name__)

# Basic Dark-Themed UI template built straight into the Python server
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Recipe Scraper</title>
    <style>
        body { background-color: #0b132b; color: #ffffff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { text-align: center; width: 100%; max-width: 600px; padding: 20px; }
        h1 { font-size: 2.5rem; margin-bottom: 5px; }
        p { color: #a5b1c2; margin-top: 0; margin-bottom: 25px; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input { flex: 1; padding: 12px; border-radius: 4px; border: 1px solid #1c2541; background-color: #1c2541; color: white; font-size: 1rem; }
        button { padding: 12px 24px; border-radius: 4px; border: none; background-color: #ffffff; color: #0b132b; font-weight: bold; cursor: pointer; font-size: 1rem; }
        button:disabled { background-color: #cccccc; cursor: not-allowed; }
        #recipe-output { margin-top: 20px; text-align: left; background: #1c2541; padding: 15px; border-radius: 6px; display: none; }
        select { padding: 6px 12px; background: #0b132b; color: white; border: 1px solid #57606f; border-radius: 4px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Recipe Scraper</h1>
        <p>Powered by Python & Render.</p>
        <div class="input-group">
            <input type="text" id="recipe-url" placeholder="https://allrecipes.com...">
            <button id="extract-btn">Extract recipe</button>
        </div>
        <div id="recipe-output">
            <h3 id="recipe-title"></h3>
            <div style="margin: 15px 0; background: #0b132b; padding: 12px; border-radius: 4px; display: flex; align-items: center; gap: 10px;">
                <label for="scale-select" style="font-weight: bold;">Scale Recipe Size:</label>
                <select id="scale-select">
                    <option value="0.5">Half Size (0.5x)</option>
                    <option value="1" selected>Original (1x)</option>
                    <option value="2">Double Size (2x)</option>
                    <option value="3">Triple Size (3x)</option>
                </select>
            </div>
            <strong>Ingredients:</strong>
            <ul id="ingredients-list"></ul>
        </div>
    </div>
    <script>
        let currentIngredients = [];

        document.getElementById("extract-btn").addEventListener("click", async () => {
            const urlInput = document.getElementById("recipe-url");
            const extractBtn = document.getElementById("extract-btn");
            const outputDiv = document.getElementById("recipe-output");
            const targetUrl = urlInput.value.trim();

            if (!targetUrl) { alert("Please paste a URL first!"); return; }

            extractBtn.textContent = "Scraping...";
            extractBtn.disabled = true;
            outputDiv.style.display = "none";

            try {
                // Fetch directly from our own Python backend endpoint
                const response = await fetch("/api/scrape", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url: targetUrl })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Extraction failed");

                currentIngredients = data.ingredients;
                document.getElementById("scale-select").value = "1";
                document.getElementById("recipe-title").textContent = data.title;
                renderIngredients(1);
                outputDiv.style.display = "block";

            } catch (error) {
                alert(`Error: ${error.message}`);
            } finally {
                extractBtn.textContent = "Extract recipe";
                extractBtn.disabled = false;
            }
        });

        document.getElementById("scale-select").addEventListener("change", (e) => {
            renderIngredients(parseFloat(e.target.value));
        });

        function renderIngredients(factor) {
            const list = document.getElementById("ingredients-list");
            list.innerHTML = "";
            currentIngredients.forEach(ing => {
                let text = ing;
                // Simple regex extraction for leading numbers/decimals/fractions
                const match = ing.match(/^(\d+\s+\d+\/\d+|\d+\/\d+|\d+\.\d+|\d+)/);
                if (match) {
                    const numStr = match[0];
                    let val = 0;
                    if (numStr.includes(' ') && numStr.includes('/')) {
                        const parts = numStr.split(/\s+/);
                        const frac = parts[1].split('/');
                        val = parseInt(parts[0]) + (parseInt(frac[0]) / parseInt(frac[1]));
                    } else if (numStr.includes('/')) {
                        const frac = numStr.split('/');
                        val = parseInt(frac[0]) / parseInt(frac[1]);
                    } else {
                        val = parseFloat(numStr);
                    }
                    const finalVal = Number((val * factor).toFixed(2)).toString();
                    text = ing.replace(numStr, finalVal);
                }
                const li = document.createElement("li");
                li.textContent = text;
                list.appendChild(li);
            });
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/scrape", methods=["POST"])
def scrape_endpoint():
    try:
        data = request.get_json() or {}
        target_url = data.get("url")
        if not target_url:
            return jsonify({"error": "Missing URL parameter"}), 400

        # Execute extraction using Python's specialized scraper module
        scraper = scrape_me(target_url, wild_mode=True)
        
        return jsonify({
            "title": scraper.title(),
            "ingredients": scraper.ingredients()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))