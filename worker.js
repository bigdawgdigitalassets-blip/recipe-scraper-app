export default {
  async fetch(request) {
    // 1. Setup absolute fallback headers to bypass browser CORS blockades
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*", 
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    // Handle browser preflight checks instantly
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed." }), {
        status: 405,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    try {
      const { recipeUrl } = await request.json();
      if (!recipeUrl) {
        return new Response(JSON.stringify({ error: "Missing URL parameter." }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      // 2. Add complete real-browser headers to prevent Allrecipes from blocking the worker
      const targetResponse = await fetch(recipeUrl, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
          "Accept-Language": "en-US,en;q=0.5",
          "Upgrade-Insecure-Requests": "1"
        }
      });

      if (!targetResponse.ok) {
        return new Response(JSON.stringify({ error: `Target site responded with status ${targetResponse.status}` }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const htmlContent = await targetResponse.text();
      
      // 3. Locate and extract the LD+JSON schema metadata blocks
      const regex = /<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
      let match;
      let recipeData = null;

      while ((match = regex.exec(htmlContent)) !== null) {
        try {
          const parsed = JSON.parse(match.trim());
          const items = Array.isArray(parsed) ? parsed : [parsed];
          for (const item of items) {
            // Check if object or any sub-graph item identifies as a recipe schema block
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
        } catch (e) {}
      }

      if (!recipeData) {
        return new Response(JSON.stringify({ error: "Could not find a structured recipe schema block on this webpage." }), {
          status: 404,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      // Return standardized structured clean list data back to frontend UI
      return new Response(JSON.stringify({
        title: recipeData.name || "Unknown Recipe",
        ingredients: recipeData.recipeIngredient || [],
      }), {
        status: 200,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }
  }
};