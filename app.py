from flask import Flask, request, jsonify, render_template_string
from curl_cffi import requests as b_requests
from recipe_scrapers import scrape_html
import json
import os

app = Flask(__name__)

# Page source posted by the bookmarklet can be a megabyte or more.
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Recipe Scraper</title>
    <style>
        body { background-color: #0b132b; color: #ffffff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; margin: 0; padding: 20px; }
        .container { text-align: center; width: 100%; max-width: 700px; }
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
        .meta { color: #a5b1c2; font-size: 0.9rem; margin: 0 0 10px 0; }
        .actions { display: flex; gap: 10px; margin-top: 20px; }
        .actions button { flex: 1; font-size: 0.9rem; padding: 10px; }
        ol li, ul li { margin-bottom: 8px; line-height: 1.4; }
        #bookmarklet-box { text-align: left; background: #12203f; border: 1px solid #2d4373; padding: 15px; border-radius: 6px; margin-top: 30px; }
        #bookmarklet-box h4 { margin: 0 0 8px 0; }
        #bookmarklet-box p, #bookmarklet-box li { color: #a5b1c2; font-size: 0.9rem; margin: 6px 0; }
        .bm-link { display: inline-block; background: #ffd166; color: #0b132b; padding: 10px 18px; border-radius: 4px; font-weight: bold; text-decoration: none; margin: 8px 0; cursor: grab; }
        .banner-error { background: #2a080c; border: 1px solid #d63031; color: #ff7675; padding: 12px; border-radius: 6px; margin-bottom: 15px; text-align: left; }
        @media print {
            body { background: #fff; color: #000; display: block; }
            .input-group, #fallback-container, .actions, .no-print, h1 + p { display: none !important; }
            #recipe-output { background: #fff; color: #000; border: none; padding: 0; }
            select { border: none; background: #fff; color: #000; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Recipe Scraper</h1>
        <p>Paste a recipe URL to get a clean, printable, scalable recipe.</p>

        <div class="banner-error no-print" id="error-banner" style="display: __ERROR_DISPLAY__;">__ERROR_TEXT__</div>

        <div class="input-group">
            <input type="text" id="recipe-url" placeholder="https://www.allrecipes.com/recipe/...">
            <button id="extract-btn">Extract recipe</button>
        </div>

        <!-- Hidden container that triggers if Cloudflare blocks the network fetch -->
        <div id="fallback-container">
            <strong style="color: #ff7675;">Firewall Blocked:</strong>
            <p style="font-size: 0.9rem; margin: 5px 0 12px 0;">This site blocked our server. The easiest fix is the <strong>Grab Recipe bookmarklet</strong> at the bottom of this page &mdash; one click and the recipe opens here automatically.</p>
            <p style="font-size: 0.9rem; margin: 5px 0 12px 0;">Or do it manually: open the recipe, right-click anywhere, select <strong>"View Page Source"</strong>, copy everything (Ctrl+A, Ctrl+C), and paste it below:</p>
            <textarea id="raw-html-input" placeholder="Paste raw page source HTML code text here..."></textarea>
            <button id="fallback-btn" style="background-color: #ff7675; color: white; width: 100%;">Parse Pasted HTML Code</button>
        </div>

        <div id="recipe-output">
            <h3 id="recipe-title"></h3>
            <p class="meta" id="recipe-meta"></p>
            <div class="no-print" style="margin: 15px 0; background: #0b132b; padding: 12px; border-radius: 4px; display: flex; align-items: center; gap: 10px;">
                <label for="scale-select" style="font-weight: bold;">Scale Recipe Size:</label>
                <select id="scale-select">
                    <option value="0.5">Half Size (0.5x)</option>
                    <option value="1" selected>Original (1x)</option>
                    <option value="1.5">One and a Half (1.5x)</option>
                    <option value="2">Double Size (2x)</option>
                    <option value="3">Triple Size (3x)</option>
                    <option value="4">Quadruple Size (4x)</option>
                </select>
            </div>
            <strong>Ingredients:</strong>
            <ul id="ingredients-list"></ul>
            <strong>Instructions:</strong>
            <ol id="instructions-list"></ol>

            <div class="actions">
                <button id="copy-btn">Copy recipe</button>
                <button id="print-btn">Print recipe</button>
            </div>
        </div>

        <div id="bookmarklet-box" class="no-print">
            <h4>Blocked by a site? Use the bookmarklet.</h4>
            <p>Some sites (Allrecipes, Food Network) block automated servers. This button runs in <em>your</em> browser instead, so there is nothing to block.</p>
            <p><strong>Setup (once):</strong> show your bookmarks bar with <code>Ctrl+Shift+B</code>, then drag this button onto it:</p>
            <p><a class="bm-link" href="__BOOKMARKLET__">Grab Recipe</a></p>
            <p><strong>Use:</strong> open any recipe page, click <strong>Grab Recipe</strong> in your bookmarks bar. The recipe opens here, ready to scale and print.</p>
            <p style="font-size: 0.8rem; color: #6c7a91;">Clicking the button here does nothing &mdash; it only works once dragged to your bookmarks bar.</p>
        </div>
    </div>

    <script>
        // Populated server-side by /import when the bookmarklet posts a page.
        const PRELOAD = __PRELOAD_JSON__;

        let currentIngredients = [];
        let currentInstructions = [];
        let currentScale = 1;

        // Core extraction function that maps JSON data to UI layouts
        function handleScrapeSuccess(data, outputDiv) {
            currentIngredients = data.ingredients || [];
            currentInstructions = data.instructions || [];
            currentScale = 1;
            document.getElementById("scale-select").value = "1";
            document.getElementById("recipe-title").textContent = data.title || "Recipe";

            const metaBits = [];
            if (data.yields) metaBits.push(data.yields);
            if (data.total_time) metaBits.push(data.total_time + " min");
            document.getElementById("recipe-meta").textContent = metaBits.join("  |  ");

            renderIngredients(1);
            renderInstructions();
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
            currentScale = parseFloat(e.target.value);
            renderIngredients(currentScale);
        });

        // Turn a decimal into a readable fraction (1.5 -> "1 1/2")
        function prettyNumber(value) {
            const rounded = Math.round(value * 1000) / 1000;
            const whole = Math.floor(rounded);
            const frac = rounded - whole;
            const table = [
                [0.125, "1/8"], [0.25, "1/4"], [0.333, "1/3"], [0.375, "3/8"],
                [0.5, "1/2"], [0.625, "5/8"], [0.667, "2/3"], [0.75, "3/4"], [0.875, "7/8"]
            ];
            for (const [dec, label] of table) {
                if (Math.abs(frac - dec) < 0.02) {
                    return whole > 0 ? `${whole} ${label}` : label;
                }
            }
            if (frac < 0.02) return String(whole);
            return String(Number(rounded.toFixed(2)));
        }

        function scaleText(text, factor) {
            // Scales every leading-or-inline quantity found in the line
            const pattern = /(\\d+\\s+\\d+\\/\\d+|\\d+\\/\\d+|\\d+\\.\\d+|\\d+)/g;
            return text.replace(pattern, (numStr) => {
                let val;
                if (numStr.includes(' ') && numStr.includes('/')) {
                    const parts = numStr.split(/\\s+/);
                    const frac = parts[1].split('/');
                    val = parseInt(parts[0]) + (parseInt(frac[0]) / parseInt(frac[1]));
                } else if (numStr.includes('/')) {
                    const frac = numStr.split('/');
                    val = parseInt(frac[0]) / parseInt(frac[1]);
                } else {
                    val = parseFloat(numStr);
                }
                return prettyNumber(val * factor);
            });
        }

        function renderIngredients(factor) {
            const list = document.getElementById("ingredients-list");
            list.innerHTML = "";
            currentIngredients.forEach(ing => {
                const li = document.createElement("li");
                li.textContent = factor === 1 ? ing : scaleText(ing, factor);
                list.appendChild(li);
            });
        }

        function renderInstructions() {
            const list = document.getElementById("instructions-list");
            list.innerHTML = "";
            currentInstructions.forEach(step => {
                const li = document.createElement("li");
                li.textContent = step;
                list.appendChild(li);
            });
        }

        function buildPlainText() {
            const title = document.getElementById("recipe-title").textContent;
            const meta = document.getElementById("recipe-meta").textContent;
            const ings = Array.from(document.querySelectorAll("#ingredients-list li")).map(li => "- " + li.textContent);
            const steps = Array.from(document.querySelectorAll("#instructions-list li")).map((li, i) => (i + 1) + ". " + li.textContent);
            const scaleNote = currentScale === 1 ? "" : `(scaled ${currentScale}x)`;
            return [title, meta, scaleNote, "", "INGREDIENTS", ...ings, "", "INSTRUCTIONS", ...steps]
                .filter(line => line !== null)
                .join("\\n");
        }

        document.getElementById("copy-btn").addEventListener("click", async () => {
            const btn = document.getElementById("copy-btn");
            const text = buildPlainText();
            try {
                await navigator.clipboard.writeText(text);
            } catch (e) {
                // Fallback for browsers/contexts without clipboard permission
                const ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
            }
            btn.textContent = "Copied!";
            setTimeout(() => { btn.textContent = "Copy recipe"; }, 1500);
        });

        document.getElementById("print-btn").addEventListener("click", () => window.print());

        // If the bookmarklet delivered a recipe, show it straight away.
        if (PRELOAD) {
            handleScrapeSuccess(PRELOAD, document.getElementById("recipe-output"));
            if (PRELOAD.source_url) document.getElementById("recipe-url").value = PRELOAD.source_url;
        }
    </script>
</body>
</html>
"""


def app_base_url():
    """Public base URL of this app, forced to https outside local dev."""
    base = request.url_root.rstrip("/")
    if base.startswith("http://") and not any(
        h in base for h in ("localhost", "127.0.0.1")
    ):
        base = "https://" + base[len("http://"):]
    return base


def make_bookmarklet(base_url):
    """
    A form POST (not fetch) so it survives the target site's Content-Security-Policy,
    needs no CORS headers, and is not caught by the popup blocker.
    """
    js = (
        "javascript:(function(){"
        "try{"
        "var f=document.createElement('form');"
        "f.method='POST';"
        "f.action='%s/import';"
        "f.target='_blank';"
        "f.style.display='none';"
        "var h=document.createElement('input');"
        "h.type='hidden';h.name='html';"
        "h.value=document.documentElement.outerHTML;"
        "f.appendChild(h);"
        "var u=document.createElement('input');"
        "u.type='hidden';u.name='url';u.value=location.href;"
        "f.appendChild(u);"
        "document.body.appendChild(f);"
        "f.submit();"
        "setTimeout(function(){f.parentNode&&f.parentNode.removeChild(f);},2000);"
        "}catch(e){alert('Grab Recipe failed: '+e.message);}"
        "})();" % base_url
    )
    # Escape only what would break out of the href="" attribute.
    return js.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def render_page(preload=None, error=None):
    payload = json.dumps(preload) if preload else "null"
    # Prevent a literal </script> inside recipe text from closing the script block.
    payload = payload.replace("</", "<\\/")

    html = HTML_TEMPLATE
    html = html.replace("__PRELOAD_JSON__", payload)
    html = html.replace("__BOOKMARKLET__", make_bookmarklet(app_base_url()))
    html = html.replace("__ERROR_DISPLAY__", "block" if error else "none")
    html = html.replace("__ERROR_TEXT__", (error or "").replace("<", "&lt;"))
    return html


@app.route("/")
def home():
    return render_page()


@app.route("/import", methods=["POST"])
def import_from_bookmarklet():
    """Receives page source posted by the bookmarklet from the user's own browser."""
    raw_html = request.form.get("html", "")
    source_url = request.form.get("url", "") or "https://www.allrecipes.com/"

    if not raw_html:
        return render_page(error="The bookmarklet sent no page content. Try again."), 400

    try:
        scraper = scrape_html(html=raw_html, org_url=source_url, wild_mode=True)
        payload = build_payload(scraper)
    except Exception as e:
        return render_page(
            error=f"Could not find a recipe on that page. ({e})"
        ), 200

    if not payload.get("ingredients"):
        return render_page(
            error="That page loaded, but no ingredients were found on it. "
                  "Make sure you clicked the bookmarklet on the recipe page itself."
        ), 200

    payload["source_url"] = source_url
    return render_page(preload=payload)


def build_payload(scraper):
    """Pull the fields we care about, tolerating scrapers that lack some of them."""
    def safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    instructions = safe(scraper.instructions_list, None)
    if not instructions:
        raw = safe(scraper.instructions, "") or ""
        instructions = [line.strip() for line in raw.split("\n") if line.strip()]

    return {
        "title": safe(scraper.title, "Recipe"),
        "ingredients": safe(scraper.ingredients, []) or [],
        "instructions": instructions,
        "yields": safe(scraper.yields, None),
        "total_time": safe(scraper.total_time, None),
    }


@app.route("/api/scrape", methods=["POST"])
def scrape_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        target_url = data.get("url")
        if not target_url:
            return jsonify({"error": "Missing URL parameter"}), 400

        response = b_requests.get(target_url, impersonate="chrome", timeout=15)

        if response.status_code != 200:
            return jsonify({
                "error": f"Firewall blocked the automatic request. Code: {response.status_code}"
            }), 502

        scraper = scrape_html(html=response.text, org_url=target_url, wild_mode=True)
        return jsonify(build_payload(scraper))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrape-raw", methods=["POST"])
def scrape_raw_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        raw_html = data.get("html")
        fallback_url = data.get("url") or "https://www.allrecipes.com/"

        if not raw_html:
            return jsonify({"error": "No HTML code text supplied."}), 400

        # Parse the copy-pasted string directly without sending any network requests
        scraper = scrape_html(html=raw_html, org_url=fallback_url, wild_mode=True)
        return jsonify(build_payload(scraper))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))