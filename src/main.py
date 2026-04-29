from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from apify import Actor
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

SEARCH_BASE = 'https://nl.kompass.com/s/'
LABEL_LISTING = 'LISTING'
LABEL_DETAIL = 'DETAIL'


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        search_query: str = actor_input.get('searchQuery', '')
        country: str = actor_input.get('country', 'NL')
        max_pages: int = actor_input.get('maxPages', 5)
        max_companies: int = actor_input.get('maxCompanies', 50)
        proxy_country: str = actor_input.get('proxyCountryCode', 'NL')

        proxy_configuration = None
        if Actor.configuration.is_at_home:
            proxy_configuration = await Actor.create_proxy_configuration(
                country_code=proxy_country or None,
            )

        crawler = PlaywrightCrawler(
            max_requests_per_crawl=max_pages + max_companies,
            proxy_configuration=proxy_configuration,
            browser_type='chromium',
        )

        @crawler.router.handler(label=LABEL_LISTING)
        async def listing_handler(context: PlaywrightCrawlingContext) -> None:
            page = context.page
            Actor.log.info(f'Zoekresultaten: {context.request.url}')

            try:
                await page.wait_for_selector(
                    '.kpdn-SerpCard, [data-cy="company-card"], .company-result',
                    timeout=20_000,
                )
            except Exception:
                Actor.log.warning('Geen bedrijfskaarten gevonden — controleer selector na testrun')
                return

            links: list[str] = await page.eval_on_selector_all(
                '.kpdn-SerpCard a[href*="/c/"], [data-cy="company-card"] a[href*="/c/"], a.company-name[href*="/c/"]',
                'els => [...new Set(els.map(el => el.href))]',
            )

            if not links:
                links = await page.eval_on_selector_all(
                    'a[href*="/c/"]',
                    'els => [...new Set(els.map(el => el.href))]',
                )

            Actor.log.info(f'{len(links)} bedrijven gevonden op deze pagina')
            await context.add_requests(
                [Request.from_url(link, label=LABEL_DETAIL) for link in links]
            )

            next_link = await page.query_selector(
                'a[rel="next"], a.pagination__next, a[aria-label="Volgende"], .pagination a:last-child'
            )
            if next_link:
                next_url = await next_link.get_attribute('href')
                if next_url and not next_url.startswith('http'):
                    next_url = f'https://nl.kompass.com{next_url}'
                if next_url:
                    Actor.log.info(f'Volgende pagina: {next_url}')
                    await context.add_requests([Request.from_url(next_url, label=LABEL_LISTING)])

        @crawler.router.handler(label=LABEL_DETAIL)
        async def detail_handler(context: PlaywrightCrawlingContext) -> None:
            page = context.page
            url = context.request.url
            Actor.log.info(f'Bedrijfspagina: {url}')

            await page.wait_for_load_state('domcontentloaded', timeout=20_000)

            async def text(selector: str) -> str:
                el = await page.query_selector(selector)
                if not el:
                    return ''
                return (await el.inner_text()).strip()

            async def attr(selector: str, attribute: str) -> str:
                el = await page.query_selector(selector)
                if not el:
                    return ''
                return (await el.get_attribute(attribute) or '').strip()

            company_name = await text(
                'h1[itemprop="name"], h1.company-name, h1.kpdn-Company-name, h1'
            )
            address = await text(
                '[itemprop="streetAddress"], .address-street, .kpdn-Address-street'
            )
            city = await text(
                '[itemprop="addressLocality"], .address-city, .kpdn-Address-city'
            )
            postal_code = await text(
                '[itemprop="postalCode"], .address-postal, .kpdn-Address-postal'
            )
            country_val = await text(
                '[itemprop="addressCountry"], .address-country, .kpdn-Address-country'
            )
            phone = await text('[itemprop="telephone"], .tel, a[href^="tel:"]')
            if phone.startswith('tel:'):
                phone = phone[4:]

            website = await attr(
                'a[itemprop="url"], a.kpdn-Company-website, a[data-cy="company-website"]',
                'href',
            )

            email = ''
            email_el = await page.query_selector('a[href^="mailto:"]')
            if email_el:
                href = await email_el.get_attribute('href') or ''
                email = href.replace('mailto:', '').split('?')[0].strip()
            else:
                reveal_btn = await page.query_selector(
                    'button[data-cy="reveal-email"], button.reveal-email, [class*="showEmail"]'
                )
                if reveal_btn:
                    try:
                        await reveal_btn.click()
                        await page.wait_for_timeout(1_500)
                        email_el = await page.query_selector('a[href^="mailto:"]')
                        if email_el:
                            href = await email_el.get_attribute('href') or ''
                            email = href.replace('mailto:', '').split('?')[0].strip()
                    except Exception:
                        pass

            description = await text(
                '[itemprop="description"], .company-description, .kpdn-Company-description'
            )
            sector = await text(
                '.sector-label, .kpdn-Activity-label, [data-cy="activity-label"]'
            )
            employees = await text(
                '[itemprop="numberOfEmployees"], .employees-count, .kpdn-Company-employees'
            )
            revenue = await text(
                '.revenue, .kpdn-Company-revenue, [data-cy="company-revenue"]'
            )

            await Actor.push_data({
                'companyName': company_name,
                'url': url,
                'address': address,
                'city': city,
                'postalCode': postal_code,
                'country': country_val or country,
                'phone': phone,
                'email': email,
                'website': website,
                'description': description,
                'sector': sector,
                'employees': employees,
                'revenue': revenue,
            })

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
