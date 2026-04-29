from __future__ import annotations

import asyncio
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
                await page.wait_for_selector('li.ant-list-item', timeout=30_000)
            except Exception:
                content_preview = (await page.content())[:500]
                Actor.log.warning(f'Geen lijst gevonden. Pagina preview: {content_preview}')
                return

            companies = await page.evaluate('''() => {
                const items = document.querySelectorAll("li.ant-list-item");
                return Array.from(items).map(item => {
                    const nameEl = item.querySelector("h1.ant-typography");
                    if (!nameEl) return null;

                    const allTags = item.querySelectorAll("span.ant-tag:not(.ant-tag-has-color)");
                    const country = allTags.length > 0 ? allTags[0].textContent.trim() : "";
                    const city    = allTags.length > 1 ? allTags[1].textContent.trim() : "";

                    const linkEl = item.querySelector("[data-testid='companyRedirector'] a, .testSponsoredRedirector a, a[href*='/company/']");
                    let url = linkEl ? linkEl.href : "";
                    if (!url) {
                        const clickable = item.querySelector("[style*='cursor: pointer']");
                        if (clickable) {
                            const anchor = clickable.closest("a") || clickable.querySelector("a");
                            if (anchor) url = anchor.href;
                        }
                    }

                    const descEl = item.querySelector("p, [class*='description'], [class*='summary']");
                    const description = descEl ? descEl.textContent.trim() : "";

                    const stars = item.querySelectorAll("li.ant-rate-star:not(.ant-rate-star-zero)").length;

                    return { companyName: nameEl.textContent.trim(), url, city, country, description, rating: stars };
                }).filter(Boolean);
            }''')

            Actor.log.info(f'{len(companies)} bedrijven gevonden')
            if companies:
                await Actor.push_data(companies)

            next_page_li = await page.query_selector('li.ant-pagination-next:not(.ant-pagination-disabled)')
            if next_page_li:
                current_url = context.request.url
                sep = '&' if '?' in current_url else '?'
                import re
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
