from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from apify import Actor
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

SEARCH_BASE = 'https://nl.kompass.com/s/'
LABEL_LISTING = 'LISTING'


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        search_query: str = actor_input.get('searchQuery', '')
        country: str = actor_input.get('country', 'NL')
        max_pages: int = actor_input.get('maxPages', 5)
        proxy_country: str = actor_input.get('proxyCountryCode', 'NL')

        proxy_configuration = None
        if Actor.configuration.is_at_home:
            proxy_configuration = await Actor.create_proxy_configuration(
                country_code=proxy_country or None,
            )

        crawler = PlaywrightCrawler(
            max_requests_per_crawl=max_pages,
            proxy_configuration=proxy_configuration,
            browser_type='chromium',
        )

        @crawler.router.handler(label=LABEL_LISTING)
        async def listing_handler(context: PlaywrightCrawlingContext) -> None:
            page = context.page
            Actor.log.info(f'Pagina: {context.request.url}')

            try:
                await page.wait_for_selector('div.prod_list', timeout=20_000)
            except Exception:
                Actor.log.warning('Geen bedrijfskaarten gevonden op deze pagina')
                return

            companies = await page.eval_on_selector_all('div.prod_list', '''
                cards => cards.map(card => {
                    const nameEl   = card.querySelector('span.titleSpan');
                    const linkEl   = card.querySelector('div.col-title a[href*="/c/"]');
                    const placeEl  = card.querySelector('span.placeText');
                    const phoneEl  = card.querySelector('input[id^="freePhone--"]');
                    const webEl    = card.querySelector('div.companyWeb a');
                    const descEl   = card.querySelector('p.product-summary span.text');
                    const sectors  = card.querySelectorAll('ul li');

                    const location = placeEl ? placeEl.textContent.trim() : '';
                    const parts    = location.split(' - ');

                    let url = linkEl ? linkEl.getAttribute('href') : '';
                    if (url && !url.startsWith('http')) url = 'https://nl.kompass.com' + url;

                    return {
                        companyName:  nameEl  ? nameEl.textContent.trim()        : '',
                        url:          url,
                        city:         parts[0] ? parts[0].trim()                 : '',
                        country:      parts[1] ? parts[1].trim()                 : '',
                        phone:        phoneEl ? phoneEl.value                    : '',
                        website:      webEl   ? webEl.getAttribute('href')       : '',
                        description:  descEl  ? descEl.textContent.trim()        : '',
                        sectors:      Array.from(sectors).map(li => li.textContent.trim()).filter(Boolean).join(', '),
                    };
                })
            ''')

            Actor.log.info(f'{len(companies)} bedrijven gevonden')
            await Actor.push_data(companies)

            next_link = await page.query_selector('a[rel="next"]')
            if next_link:
                next_url = await next_link.get_attribute('href') or ''
                if next_url and not next_url.startswith('http'):
                    next_url = f'https://nl.kompass.com{next_url}'
                if next_url:
                    Actor.log.info(f'Volgende pagina: {next_url}')
                    await context.add_requests([Request.from_url(next_url, label=LABEL_LISTING)])

        params: dict[str, str] = {}
        if search_query:
            params['text'] = search_query
        if country:
            params['country'] = country
        start_url = SEARCH_BASE + ('?' + urlencode(params) if params else '')
        Actor.log.info(f'Start URL: {start_url}')

        await crawler.run([Request.from_url(start_url, label=LABEL_LISTING)])


if __name__ == '__main__':
    asyncio.run(main())
