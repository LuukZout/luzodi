from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from urllib.parse import urlencode

from apify import Actor
from crawlee import ConcurrencySettings, Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext, PlaywrightPreNavCrawlingContext
from playwright_stealth import Stealth

SEARCH_BASE = 'https://www.b2bstars.com/nl/kompass/company'
LABEL_LISTING = 'LISTING'

_stealth = Stealth()


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        search_query: str = actor_input.get('searchQuery', '')
        countries: str = actor_input.get('countries', 'NL')
        max_pages: int = actor_input.get('maxPages', 5)

        proxy_configuration = None
        if Actor.configuration.is_at_home:
            proxy_configuration = await Actor.create_proxy_configuration(
                groups=['RESIDENTIAL'],
            )

        crawler = PlaywrightCrawler(
            headless=True,
            max_requests_per_crawl=max_pages,
            proxy_configuration=proxy_configuration,
            max_request_retries=5,
            max_session_rotations=15,
            request_handler_timeout=timedelta(minutes=10),
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1,
                max_concurrency=1,
                desired_concurrency=1,
            ),
        )

        @crawler.pre_navigation_hook
        async def before_nav(context: PlaywrightPreNavCrawlingContext) -> None:
            await _stealth.apply_stealth_async(context.page.context)

        @crawler.router.handler(label=LABEL_LISTING)
        async def listing_handler(context: PlaywrightCrawlingContext) -> None:
            page = context.page
            Actor.log.info(f'Pagina: {context.request.url}')

            try:
                await page.wait_for_selector('li.ant-list-item h1.ant-typography', timeout=30_000)
            except Exception:
                content_preview = (await page.content())[:500]
                Actor.log.warning(f'Geen lijst gevonden. Pagina preview: {content_preview}')
                return

            # Extract listing data (name, city, country, sectors, rating)
            companies = await page.evaluate('''() => {
                const items = document.querySelectorAll("li.ant-list-item");
                return Array.from(items).map(item => {
                    const nameEl = item.querySelector("h1.ant-typography");
                    if (!nameEl) return null;

                    // All tags: [0]=country, [1]=city, [2:]=sectors
                    const allTags = Array.from(item.querySelectorAll("span.ant-tag"));
                    const country = allTags.length > 0 ? allTags[0].textContent.trim() : "";
                    const city    = allTags.length > 1 ? allTags[1].textContent.trim() : "";
                    const sectors = allTags.slice(2).map(t => t.textContent.trim()).filter(Boolean).join(", ");
                    const stars   = item.querySelectorAll("li.ant-rate-star-full").length;

                    return { companyName: nameEl.textContent.trim(), city, country, sectors, rating: stars, url: "" };
                }).filter(Boolean);
            }''')
            Actor.log.info(f'{len(companies)} bedrijven gevonden')

            # Click each company to capture profile URL via SPA navigation.
            # Match by name each time since DOM order can change after go_back.
            listing_url = context.request.url
            for company in companies:
                name = company['companyName']
                try:
                    await page.wait_for_selector('li.ant-list-item h1.ant-typography', timeout=10_000)

                    # Find the h1 that matches this company by text
                    target_h1 = None
                    for li in await page.query_selector_all('li.ant-list-item'):
                        h1 = await li.query_selector('h1.ant-typography')
                        if h1 and (await h1.inner_text()).strip() == name:
                            target_h1 = h1
                            break

                    if not target_h1:
                        Actor.log.warning(f'  {name}: niet gevonden in DOM, overgeslagen')
                        continue

                    pre_url = page.url
                    await target_h1.click()
                    await page.wait_for_function(
                        f'window.location.href !== {repr(pre_url)}',
                        timeout=10_000,
                    )
                    company['url'] = page.url.split('?')[0]

                    # Extract contact data from the detail page while we're here
                    await page.wait_for_timeout(1500)
                    contact = await page.evaluate('''() => {
                        const CONTACT_FIELDS = ["website", "phone", "email", "address", "fax"];
                        const result = {};
                        for (const el of document.querySelectorAll("[data-track]")) {
                            const track = el.dataset.track;
                            if (CONTACT_FIELDS.includes(track)) {
                                const text = el.textContent.trim();
                                if (text && !result[track]) result[track] = text;
                            }
                        }
                        // Normalise website to a full URL
                        if (result.website && !result.website.startsWith("http")) {
                            result.website = "https://" + result.website;
                        }
                        return result;
                    }''')
                    company.update(contact)
                    Actor.log.info(f'  {name}: {company["url"]} | web={contact.get("website","")} tel={contact.get("phone","")}')

                    await page.go_back(wait_until='domcontentloaded')

                except Exception as e:
                    Actor.log.warning(f'URL capture mislukt voor {name}: {e}')
                    if page.url != listing_url:
                        try:
                            await page.go_back(wait_until='domcontentloaded')
                        except Exception:
                            await page.goto(listing_url, wait_until='domcontentloaded')

            await Actor.push_data(companies)

            # Pagination
            next_page_li = await page.query_selector('li.ant-pagination-next:not(.ant-pagination-disabled)')
            if next_page_li:
                current_url = context.request.url
                sep = '&' if '?' in current_url else '?'
                if re.search(r'[?&]page=(\d+)', current_url):
                    next_url = re.sub(r'([?&]page=)(\d+)', lambda m: m.group(1) + str(int(m.group(2)) + 1), current_url)
                else:
                    next_url = current_url + sep + 'page=2'
                Actor.log.info(f'Volgende pagina: {next_url}')
                await context.add_requests([Request.from_url(next_url, label=LABEL_LISTING)])

        params: dict[str, str] = {}
        if search_query:
            params['q'] = search_query
        if countries:
            params['countries'] = countries
        start_url = SEARCH_BASE + ('?' + urlencode(params) if params else '')
        Actor.log.info(f'Start URL: {start_url}')

        await crawler.run([Request.from_url(start_url, label=LABEL_LISTING)])


if __name__ == '__main__':
    asyncio.run(main())
