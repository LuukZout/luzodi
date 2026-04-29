from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from apify import Actor
from crawlee import Request
from crawlee.crawlers import CurlImpersonateCrawler, CurlImpersonateCrawlingContext

SEARCH_BASE = 'https://nl.kompass.com/s/'
LABEL_LISTING = 'LISTING'


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        search_query: str = actor_input.get('searchQuery', '')
        country: str = actor_input.get('country', 'NL')
        max_pages: int = actor_input.get('maxPages', 5)

        proxy_configuration = None
        if Actor.configuration.is_at_home:
            proxy_configuration = await Actor.create_proxy_configuration(
                groups=['RESIDENTIAL'],
            )

        crawler = CurlImpersonateCrawler(
            impersonate='chrome131',
            max_requests_per_crawl=max_pages,
            proxy_configuration=proxy_configuration,
            max_request_retries=3,
        )

        @crawler.router.handler(label=LABEL_LISTING)
        async def listing_handler(context: CurlImpersonateCrawlingContext) -> None:
            soup = context.soup
            Actor.log.info(f'Pagina: {context.request.url}')

            cards = soup.select('div.prod_list')
            if not cards:
                Actor.log.warning('Geen bedrijfskaarten gevonden op deze pagina')
                return

            companies = []
            for card in cards:
                name_el  = card.select_one('span.titleSpan')
                link_el  = card.select_one('div.col-title a[href*="/c/"]')
                place_el = card.select_one('span.placeText')
                phone_el = card.select_one('input[id^="freePhone--"]')
                web_el   = card.select_one('div.companyWeb a')
                desc_el  = card.select_one('p.product-summary span.text')
                sector_els = card.select('ul li')

                location = place_el.get_text(strip=True) if place_el else ''
                parts = location.split(' - ', 1)

                url = link_el.get('href', '') if link_el else ''
                if url and not url.startswith('http'):
                    url = f'https://nl.kompass.com{url}'

                companies.append({
                    'companyName': name_el.get_text(strip=True) if name_el else '',
                    'url':         url,
                    'city':        parts[0].strip() if parts else '',
                    'country':     parts[1].strip() if len(parts) > 1 else '',
                    'phone':       phone_el.get('value', '') if phone_el else '',
                    'website':     web_el.get('href', '') if web_el else '',
                    'description': desc_el.get_text(strip=True) if desc_el else '',
                    'sectors':     ', '.join(
                        li.get_text(strip=True) for li in sector_els
                        if li.get_text(strip=True)
                    ),
                })

            Actor.log.info(f'{len(companies)} bedrijven gevonden')
            await Actor.push_data(companies)

            next_link = soup.select_one('a[rel="next"]')
            if next_link:
                next_url = next_link.get('href', '')
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
