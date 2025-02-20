import asyncio

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from markdownify import markdownify as md
from markdownify import MarkdownConverter

async def main() -> None:
    crawler = BeautifulSoupCrawler(
        # Limit the crawl to max requests. Remove or increase it for crawling all links.
        max_requests_per_crawl=10,
    )

    # Define the default request handler, which will be called for every request.
    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        context.log.info(f'Processing {context.request.url} ...')

        # Extract data from the page.
        data = {
            'url': context.request.url,
            'title': context.soup.title.string if context.soup.title else None,
            'markdown': md(str(context.soup)),
        }

        # Push the extracted data to the default dataset.
        await context.push_data(data)

        # Enqueue all links found on the page.
        await context.enqueue_links()

    # Run the crawler with the initial list of URLs.
    await crawler.run(['https://crawlee.dev'])
    await crawler.export_data_json('crawlee_data.json')
    data = await crawler.get_data()
    crawler.log.info(f'Extracted data: {data.items}')
    
    # save markdown 0 to test.md
    with open('test.md', 'w') as f:
        f.write(data.items[0]['markdown'])

if __name__ == '__main__':
    asyncio.run(main())
    
    
    
# import asyncio

# from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext


# async def main() -> None:
#     crawler = PlaywrightCrawler(
#         # Limit the crawl to max requests. Remove or increase it for crawling all links.
#         max_requests_per_crawl=10,
#     )

#     # Define the default request handler, which will be called for every request.
#     @crawler.router.default_handler
#     async def request_handler(context: PlaywrightCrawlingContext) -> None:
#         context.log.info(f'Processing {context.request.url} ...')

#         # Extract data from the page.
#         data = {
#             'url': context.request.url,
#             'title': await context.page.title(),
#         }

#         # Push the extracted data to the default dataset.
#         await context.push_data(data)

#         # Enqueue all links found on the page.
#         await context.enqueue_links()

#     # Run the crawler with the initial list of requests.
#     await crawler.run(['https://crawlee.dev'])


# if __name__ == '__main__':
#     asyncio.run(main())