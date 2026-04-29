# Kompass B2B Contact Scraper

Extract company contact data from [nl.kompass.com](https://nl.kompass.com) — the largest B2B business directory in the Netherlands and Belgium. Search by keyword, sector, or company name and collect structured contact information at scale.

## What it does

This Actor crawls Kompass search results and extracts the following data for each company:

| Field | Description |
|---|---|
| `companyName` | Official company name |
| `url` | Kompass profile URL |
| `city` | City |
| `country` | Country (e.g. Nederland, België) |
| `phone` | Phone number |
| `website` | Company website URL |
| `description` | Short company description |
| `sectors` | Products/services the company supplies |

## Input

| Parameter | Type | Default | Description |
|---|---|---|---|
| `searchQuery` | string | *(empty)* | Keyword, sector, or company name to search for |
| `country` | string | `NL` | ISO country code to filter results (`NL`, `BE`, `DE`, etc.) |
| `maxPages` | integer | `5` | Maximum number of search result pages to scrape |
| `proxyCountryCode` | string | `NL` | Preferred proxy country (requires paid Apify plan) |

### Example input

```json
{
  "searchQuery": "software",
  "country": "NL",
  "maxPages": 3
}
```

## Output

Results are stored in the **Dataset** tab after each run. Each item represents one company:

```json
{
  "companyName": "Ampco Metal S.A.",
  "url": "https://nl.kompass.com/c/ampco-metal-s-a/nl142595/",
  "city": "Woerden",
  "country": "Nederland",
  "phone": "+31 348 416 706",
  "website": "http://www.ampcometal.com",
  "description": "Al meer dan een eeuw helpen wij de technische problemen van onze klanten op te lossen...",
  "sectors": "Aluminiumbrons, Aluminiumnikkelbrons, Berylliumkopervervanger"
}
```

You can export results as **JSON**, **CSV**, or **Excel** directly from the Apify Console.

## Use cases

- **Sales prospecting** — Build targeted B2B lead lists by sector or region
- **Market research** — Map out competitors and suppliers in a specific industry
- **CRM enrichment** — Add missing contact data to existing company lists
- **Partner sourcing** — Find suppliers or distributors in the Netherlands or Belgium

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

> **Note:** Running locally without a proxy will likely result in 403 blocks from Kompass. Deploy to Apify for reliable results using their proxy network.

### Deploy to Apify

```bash
apify login
apify push
```

Then start a run from the [Apify Console](https://console.apify.com).

## Notes

- Kompass uses bot detection (Cloudflare). A **residential proxy** is recommended for reliable scraping — available on the Apify Personal plan or via an external proxy provider.
- Email addresses are not included in the output. Kompass loads these via a separate authenticated request after a user interaction.
- Results per page vary between 10–25 companies depending on the search query.

## Built by

**Luzodi** — [github.com/LuukZout/luzodi](https://github.com/LuukZout/luzodi)
