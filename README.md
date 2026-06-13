# FitFindr

FitFindr is a multi tool AI agent for thrifting. u type what ur after in plain english (like "vintage graphic tee under $30") n it runs 3 tools in order: `search_listings` digs thru the mock secondhand listings n ranks the matches, `suggest_outfit` takes the top find + ur existing wardrobe n builds actual outfits, n `create_fit_card` writes a short shareable OOTD caption for it. the whole point isnt the search, its the agent part: a planning loop that decides which tool to call based on what came back, passes state between the tools so u never re enter anything, n fails gracefully when a tool comes back w nothing (eg an impossible query stops after the search n tells u what to change instead of crashing or styling an item that doesnt exist).

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```


## Fork the FitFindr starter repo, then clone your fork locally.

Create and activate a virtual environment from inside your cloned repo:
```bash
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
source .venv/Scripts/activate      # Windows (Git Bash)
# or: .venv\Scripts\activate       # Windows (Command Prompt)
```
You should see (.venv) in your terminal prompt.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
