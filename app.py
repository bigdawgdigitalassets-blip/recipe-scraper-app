from flask import Flask, request, jsonify, render_template_string
from curl_cffi import requests as b_requests
from recipe_scrapers import scrape_html
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Recipe Scraper</title>
    <style>
        body { background-color: #0b132b; color: #ffffff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .container { text-align: center; width: 100%; max-width: 600px; }
        h1 { font-size: 2.5rem; margin-bottom: 5px; }
        p { color: #a5b1c2; margin-top: 0; margin-bottom: 25px; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input, textarea { flex: 1; padding: 12px; border-radius: 4px; border: 1px solid #1c2541; background-color: #1c2541; color: white; font-size: 1rem; }
        textarea { width: 100%; height: 150px; resize: vertical; display: none; margin-bottom: 15px; box-sizing: border-box; }
        button { padding: 12px 24px; border-radius: 4px; border: none; background-color: #ffffff; color: #0b132b; font-weight: bold; cursor: pointer; font-size: 1rem; }
        button:disabled { background-color: #cccccc; cursor: not-allowed; }
        #fallback-container { display: none; background: #2a080c; border: 1px solid #d63031; padding: 15px; border-radius: 6px; text-align: left; margin-bottom: 20px; }
        #recipe-output { margin-top: 20px; text-align: left; background: #1c2541; padding: 15px; border-radius: 6px; display: none; }
        select { padding: 6px 12px; background: #0b132b; color: white; border: 1px solid #57606f; border-radius: 4px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Recipe Scraper</h1>
        <p>Bypass firewall blocks with automated fallback layouts.</p>
        
        <div class="input-group">
            <input type="text" id="recipe-url" placeholder="https://www.allrecipes.com/recipe/...">
            <button id="extract-btn">Extract recipe</button>
        </div>

        <!-- Hidden container that triggers if Cloudflare blocks the network fetch -->
        <div id="fallback-container">
            <strong style="color: #ff7675;">Firewall Blocked (Code 402/403):</strong>
            <p style="font-size: 0.9rem; margin: 5px 0 12px 0;">Allrecipes blocked our automated server. To bypass it: Open the recipe link in a new tab, right-click anywhere, select <strong>"View Page Source"</strong>, copy everything (Ctrl+A, Ctrl+C), and paste it below:</p>
            <textarea id="raw-html-input" placeholder="Paste raw page source HTML code text here..."></textarea>
            <button id="fallback-btn" style="background-color: #ff7675; color: white; width: 100%;">Parse Pasted HTML Code</button>
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

        // Core extraction function that maps JSON data to UI layouts
        function handleScrapeSuccess(data, outputDiv) {
            currentIngredients = data.ingredients;
            document.getElementById("scale-select").value = "1";
            document.getElementById("recipe-title").textContent = data.title;
            renderIngredients(1);
            outputDiv.style.display = "block";
            document.getElementById("fallback-container").style.display = "none";
        }

        // Action 1: Automated URL Scrape
        document.getElementById("extract-btn").addEventListener("click", async () => {
            const urlInput = document.getElementById("recipe-url");
            const extractBtn = document.getElementById("extract-btn");
            const outputDiv = document.getElementById("recipe-output");
            const fallbackDiv = document.getElementById("fallback-container");
            const targetUrl = urlInput.value.trim();

            if (!targetUrl) { alert("Please paste a URL first!"); return; }

            extractBtn.textContent = "Scraping...";
            extractBtn.disabled = true;
            outputDiv.style.display = "none";
            fallbackDiv.style.display = "none";

            try {
                const response = await fetch("/api/scrape", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url: targetUrl })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Blocked");

                handleScrapeSuccess(data, outputDiv);

            } catch (error) {
                console.error(error);
                // Trigger fallback option layout on error
                fallbackDiv.style.display = "block";
                document.getElementById("raw-html-input").style.display = "block";
            } finally {
                extractBtn.textContent = "Extract recipe";
                extractBtn.disabled = false;
            }
        });

        // Action 2: Manual HTML Copy-Paste Fallback Parsing
        document.getElementById("fallback-btn").addEventListener("click", async () => {
            const htmlText = document.getElementById("raw-html-input").value.trim();
            const targetUrl = document.getElementById("recipe-url").value.trim();
            const outputDiv = document.getElementById("recipe-output");

            if (!htmlText) { alert("Please paste the page source HTML code first!"); return; }

            try {
                const response = await fetch("/api/scrape-raw", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ html: htmlText, url: targetUrl })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Failed to process text code.");

                handleScrapeSuccess(data, outputDiv);

            } catch (error) {
                alert(`Parsing Error: ${error.message}`);
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

        response = b_requests.get(target_url, impersonate="chrome", timeout=15)
        
        if response.status_code != 200:
            return jsonify({"error": f"Cloudflare Firewall blocked the automatic request. Code: {response.status_code}"}), response.status_code

        scraper = scrape_html(html=response.text, org_url=target_url, wild_mode=True)
        return jsonify({"title": scraper.title(), "ingredients": scraper.ingredients()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scrape-raw", methods=["POST"])
def scrape_raw_endpoint():
    try:
        data = request.get_json() or {}
        raw_html = data.get("html")
        fallback_url = data.get("url") or "https://www.allrecipes.com/"
        
        if not raw_html:
            return jsonify({"error": "No HTML code text supplied."}), 400

        # Parse the copy-pasted string directly without sending any network requests
        scraper = scrape_html(html=raw_html, org_url=fallback_url, wild_mode=True)
        return jsonify({"title": scraper.title(), "ingredients": scraper.ingredients()})
    except Exception as e:return jsonify({"error": str(e)}), 500if name == "main":app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))