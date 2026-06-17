# FitFindr 🛍️

**Author:** Elaheh Baharlouei

FitFindr is a multi-tool AI agent designed to help users find secondhand clothing and seamlessly style those pieces with their existing digital wardrobe. The agent orchestrates a custom planning loop, connecting a local search algorithm with Groq-powered LLMs to deliver personalized fashion advice and shareable social media captions through a Gradio interface.

## 🚀 Setup & Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Variables:**
   Set your Groq API key in a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_key_here
   ```
3. **Run the Application:**
   ```bash
   python app.py
   ```

## 🏗️ Architecture

FitFindr operates using a conditional planning loop rather than a rigid, sequential chain. The diagram below illustrates how the agent branches its logic based on the success or failure of the initial search tool.

```mermaid
flowchart TD
    A["User Query & Wardrobe"] --> B["Initialize Session & Parse Query"]
    B --> C[search_listings]
    
    C -- "results = []" --> D["Set session['error'] & Return early"]
    C -- "results = [item, ...]" --> E["Session: selected_item = results 0"]
    
    E --> F[suggest_outfit]
    F --> G["Session: outfit_suggestion = output"]
    
    G --> H[create_fit_card]
    H --> I["Session: fit_card = output"]
    
    I --> J["Return completed session"]
    D --> J
    
## 🧠 State Management

State is tracked entirely within a single `session` dictionary that is initialized at the start of the interaction. 
1. **Parsing:** The agent extracts explicit constraints like maximum price and size.
2. **Conditional Branching:** If the search returns empty, it exits early to prevent LLM errors. If items are found, the top item is saved to `session["selected_item"]` and passed to the subsequent generation tools.

## 🛠️ Tool Inventory

* **`search_listings(description: str, size: str | None, max_price: float | None) -> list[dict]`**
  Searches the local dataset using price/size filters and returns matching items based on keyword overlap.
* **`suggest_outfit(new_item: dict, wardrobe: dict) -> str`**
  Uses the Groq API to recommend specific outfit pairings based on the user's existing closet.
* **`create_fit_card(outfit: str, new_item: dict) -> str`**
  Takes the generated outfit and writes a short, engaging social media caption.

## 🛡️ Error Handling & Graceful Degradation

I deliberately built failure modes to ensure the agent degrades gracefully:
* **`search_listings`:** Querying an impossible item (e.g., a $5 designer ballgown) returns `[]`. The loop catches this and displays a friendly error instead of crashing.
* **`suggest_outfit`:** If you select the "Empty Wardrobe" path, it dynamically adapts the prompt to give general styling advice instead of breaking.
* **`create_fit_card`:** If passed an empty outfit string, it bypasses the API completely and returns a hardcoded error: *"Could not generate fit card: outfit details missing."*

## 📝 Spec Reflection

The final implementation tightly aligns with my `planning.md` file. The core logic of the planning loop—specifically the conditional branching after the search tool—works exactly as diagrammed. State passes cleanly between the tools without any hardcoded leaks.

## 🤖 AI Usage

I used AI to help speed up boilerplate code, but heavily modified the outputs to fit my architecture:
1. **API Implementation:** I gave the AI my `suggest_outfit` spec and the wardrobe JSON format. It generated the API call, but I had to override the model choice, changing it to `llama-3.3-70b-versatile` because the AI's suggested model was deprecated.
2. **Planning Loop:** I provided my planning logic for the `run_agent` function. The AI generated a basic pass-through loop, but I manually modified it by adding a custom `re.search()` regex parser at the top to cleanly extract sizes and prices from the natural language query.