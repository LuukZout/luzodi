# B2BStars / Kompass Company Scraper

Extract B2B company contact data from [b2bstars.com](https://www.b2bstars.com) — a Kompass partner site covering millions of companies across Europe. Search by keyword, sector, or country and collect structured contact information at scale.

## What it does

This Actor crawls B2BStars search results and extracts the following data for each company:

| Field | Description |
|---|---|
| `companyName` | Official registered company name |
| `url` | B2BStars profile URL |
| `website` | Company website URL |
| `phone` | Phone number (may be empty — gated behind B2BStars paywall) |
| `email` | Email address |
| `address` | Street address |
| `city` | City |
| `country` | Country |
| `sectors` | Comma-separated industry sectors |
| `rating` | Kompass star rating (0–5) |

## Input

| Parameter | Type | Default | Description |
|---|---|---|---|
| `searchQuery` | string | *(empty)* | Keyword, sector, or company name to search for |
| `countries` | string | `NL` | Comma-separated ISO country codes (`NL`, `BE`, `DE`, etc.) |
| `maxPages` | integer | `5` | Maximum number of search result pages to scrape |

### Example input

```json
{
  "searchQuery": "software",
  "countries": "NL",
  "maxPages": 3
}
```

## Output

Results are stored in the **Dataset** tab after each run. Each item represents one company:

```json
{
  "companyName": "Qlic Internet Solutions B.V.",
  "url": "https://www.b2bstars.com/nl/kompass/company/qlic-internet-solutions-bv",
  "website": "https://qlic.nl",
  "phone": "",
  "email": "",
  "address": "",
  "city": "Amsterdam",
  "country": "Nederland",
  "sectors": "Internet services, Software development",
  "rating": 3
}
```

You can export results as **JSON**, **CSV**, or **Excel** directly from the Apify Console.

## Use cases

- **Sales prospecting** — Build targeted B2B lead lists by sector or region
- **Market research** — Map out competitors and suppliers in a specific industry
- **CRM enrichment** — Add missing contact data to existing company lists
- **Partner sourcing** — Find suppliers or distributors across Europe

## Setup & running locally

### Requirements

- Python 3.10+
- [Apify CLI](https://docs.apify.com/cli)

### Installation

```bash
git clone https://github.com/LuukZout/luzodi.git
cd luzodi
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

### Run locally

Edit `storage/key_value_stores/default/INPUT.json` to set your search parameters, then:

```bash
apify run
```

> **Note:** Running locally without a proxy may result in blocks. Deploy to Apify for reliable results using their residential proxy network.

### Deploy to Apify

```bash
apify login
apify push
```

Then start a run from the [Apify Console](https://console.apify.com).

## Notes

- Phone numbers are hidden behind the B2BStars paywall and will be empty in output.
- Results per page vary between 10–25 companies depending on the search query.
- The Actor uses stealth Playwright to bypass bot detection.

## Built by

**Luzodi** — [github.com/LuukZout/luzodi](https://github.com/LuukZout/luzodi)
