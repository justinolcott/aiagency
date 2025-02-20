
Crawlee · Build reliable crawlers. Fast.[Skip to main content](#__docusaurus_skipToContent_fallback)[![](/img/crawlee-light.svg)![](/img/crawlee-dark.svg)**Crawlee**](/)[Docs](/docs/quick-start)[Examples](/docs/examples)[API](/api/core)[Changelog](/api/core/changelog)[Blog](/blog)[Node.js](#)

* [Node.js](#)
* [Python](https://crawlee.dev/python)
[3.12](/docs/quick-start)

* [Next](/docs/next/quick-start)
* [3.12](/docs/quick-start)
* [3.11](/docs/3.11/quick-start)
* [3.10](/docs/3.10/quick-start)
* [3.9](/docs/3.9/quick-start)
* [3.8](/docs/3.8/quick-start)
* [3.7](/docs/3.7/quick-start)
* [3.6](/docs/3.6/quick-start)
* [3.5](/docs/3.5/quick-start)
* [3.4](/docs/3.4/quick-start)
* [3.3](/docs/3.3/quick-start)
* [3.2](/docs/3.2/quick-start)
* [3.1](/docs/3.1/quick-start)
* [3.0](/docs/3.0/quick-start)
* [2.2](https://sdk.apify.com/docs/guides/getting-started)
* [1.3](https://sdk.apify.com/docs/1.3.1/guides/getting-started)
[GitHub](https://github.com/apify/crawlee "View on GitHub")[Discord](https://discord.com/invite/jyEM2PRvMU "Chat on Discord")Search

Crawlee is a web scraping and browser automation library
========================================================

Crawlee is a web scraping and browser automation library
========================================================

It helps you build reliable crawlers. Fast.
-------------------------------------------

[Get Started](/docs/introduction)![](/assets/images/logo-blur-f5954a6b7743aa97a2653c9510a62510.png)
```
npx crawlee create my-crawler  

```

Reliable crawling 🏗️
--------------------

Crawlee won't fix broken selectors for you (yet), but it helps you **build and maintain your crawlers faster**.

When a website adds [JavaScript rendering](https://crawlee.dev/docs/guides/javascript-rendering), you don't have to rewrite everything, only switch to one of the browser crawlers. When you later find a great API to speed up your crawls, flip the switch back.

It keeps your proxies healthy by rotating them smartly with good fingerprints that make your crawlers look human-like. It's not unblockable, but [**it will save you money in the long run**](https://blog.apify.com/daltix-python-vs-apify-sdk/).

Crawlee is built by people who scrape for a living and use it every day to scrape millions of pages. [**Meet our community on Discord**](https://discord.com/invite/jyEM2PRvMU).

### JavaScript & TypeScript

We believe websites are best scraped in the language they're written in. Crawlee **runs on Node.js and it's [built in TypeScript](https://crawlee.dev/docs/guides/typescript-project)** to improve code completion in your IDE, even if you don't use TypeScript yourself. Crawlee supports both TypeScript and JavaScript crawling.

### HTTP scraping

Crawlee makes HTTP requests that [**mimic browser headers and TLS fingerprints**](https://crawlee.dev/docs/guides/avoid-blocking). It also rotates them automatically based on data about real-world traffic. Popular HTML parsers **[Cheerio](https://crawlee.dev/docs/guides/cheerio-crawler-guide)  and [JSDOM](https://crawlee.dev/docs/guides/jsdom-crawler-guide)** are included.

### Headless browsers

Switch your crawlers from HTTP to [headless browsers](https://crawlee.dev/docs/guides/javascript-rendering) in 3 lines of code. Crawlee builds on top of **Puppeteer and Playwright** and adds its own **anti-blocking features and human-like fingerprints**. Chrome, Firefox and more.

### Automatic scaling and proxy management

Crawlee automatically manages concurrency based on [available system resources](https://crawlee.dev/api/core/class/AutoscaledPool) and [smartly rotates proxies](https://crawlee.dev/docs/guides/proxy-management). Proxies that often time-out, return network errors or bad HTTP codes like 401 or 403 are discarded.

### Queue and Storage

You can [save files, screenshots and JSON results](https://crawlee.dev/docs/guides/result-storage) to disk with one line of code or plug an adapter for your DB. Your URLs are [kept in a queue](https://crawlee.dev/docs/guides/request-storage) that ensures their uniqueness and that you don't lose progress when something fails.

### Helpful utils and configurability

Crawlee includes tools for [extracting social handles](https://crawlee.dev/api/utils/namespace/social) or phone numbers, infinite scrolling, blocking unwanted assets [and many more](https://crawlee.dev/api/utils). It works great out of the box, but also provides [rich configuration options](https://crawlee.dev/api/basic-crawler/interface/BasicCrawlerOptions).

Try Crawlee out 👾
-----------------

before you startCrawlee requires [**Node.js 16 or higher**](https://nodejs.org/en/).

The fastest way to try Crawlee out is to use the **Crawlee CLI** and choose the **[Getting started](https://crawlee.dev/docs/quick-start) example**. The CLI will install all the necessary dependencies and add boilerplate code for you to play with.

```
npx crawlee create my-crawler  

```

If you prefer adding Crawlee **into your own project**, try the example below. Because it uses `PlaywrightCrawler` we also need to install Playwright. It's not bundled with Crawlee to reduce install size.

```
npm install crawlee playwright  

```
[Run on](https://console.apify.com/actors/6i5QsHBMtm3hKph70?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcbiAgICBcImNvZGVcIjogXCJpbXBvcnQgeyBQbGF5d3JpZ2h0Q3Jhd2xlciB9IGZyb20gJ2NyYXdsZWUnO1xcblxcbi8vIENyYXdsZXIgc2V0dXAgZnJvbSB0aGUgcHJldmlvdXMgZXhhbXBsZS5cXG5jb25zdCBjcmF3bGVyID0gbmV3IFBsYXl3cmlnaHRDcmF3bGVyKHtcXG4gICAgLy8gVXNlIHRoZSByZXF1ZXN0SGFuZGxlciB0byBwcm9jZXNzIGVhY2ggb2YgdGhlIGNyYXdsZWQgcGFnZXMuXFxuICAgIGFzeW5jIHJlcXVlc3RIYW5kbGVyKHsgcmVxdWVzdCwgcGFnZSwgZW5xdWV1ZUxpbmtzLCBwdXNoRGF0YSwgbG9nIH0pIHtcXG4gICAgICAgIGNvbnN0IHRpdGxlID0gYXdhaXQgcGFnZS50aXRsZSgpO1xcbiAgICAgICAgbG9nLmluZm8oYFRpdGxlIG9mICR7cmVxdWVzdC5sb2FkZWRVcmx9IGlzICcke3RpdGxlfSdgKTtcXG5cXG4gICAgICAgIC8vIFNhdmUgcmVzdWx0cyBhcyBKU09OIHRvIC4vc3RvcmFnZS9kYXRhc2V0cy9kZWZhdWx0XFxuICAgICAgICBhd2FpdCBwdXNoRGF0YSh7IHRpdGxlLCB1cmw6IHJlcXVlc3QubG9hZGVkVXJsIH0pO1xcblxcbiAgICAgICAgLy8gRXh0cmFjdCBsaW5rcyBmcm9tIHRoZSBjdXJyZW50IHBhZ2VcXG4gICAgICAgIC8vIGFuZCBhZGQgdGhlbSB0byB0aGUgY3Jhd2xpbmcgcXVldWUuXFxuICAgICAgICBhd2FpdCBlbnF1ZXVlTGlua3MoKTtcXG4gICAgfSxcXG5cXG4gICAgLy8gVW5jb21tZW50IHRoaXMgb3B0aW9uIHRvIHNlZSB0aGUgYnJvd3NlciB3aW5kb3cuXFxuICAgIC8vIGhlYWRsZXNzOiBmYWxzZSxcXG5cXG4gICAgLy8gQ29tbWVudCB0aGlzIG9wdGlvbiB0byBzY3JhcGUgdGhlIGZ1bGwgd2Vic2l0ZS5cXG4gICAgbWF4UmVxdWVzdHNQZXJDcmF3bDogMjAsXFxufSk7XFxuXFxuLy8gQWRkIGZpcnN0IFVSTCB0byB0aGUgcXVldWUgYW5kIHN0YXJ0IHRoZSBjcmF3bC5cXG5hd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYnXSk7XFxuXFxuLy8gRXhwb3J0IHRoZSBlbnRpcmV0eSBvZiB0aGUgZGF0YXNldCB0byBhIHNpbmdsZSBmaWxlIGluXFxuLy8gLi9zdG9yYWdlL2tleV92YWx1ZV9zdG9yZXMvcmVzdWx0LmNzdlxcbmNvbnN0IGRhdGFzZXQgPSBhd2FpdCBjcmF3bGVyLmdldERhdGFzZXQoKTtcXG5hd2FpdCBkYXRhc2V0LmV4cG9ydFRvQ1NWKCdyZXN1bHQnKTtcXG5cXG4vLyBPciB3b3JrIHdpdGggdGhlIGRhdGEgZGlyZWN0bHkuXFxuY29uc3QgZGF0YSA9IGF3YWl0IGNyYXdsZXIuZ2V0RGF0YSgpO1xcbmNvbnNvbGUudGFibGUoZGF0YS5pdGVtcyk7XFxuXCJcbn0iLCJvcHRpb25zIjp7ImNvbnRlbnRUeXBlIjoiYXBwbGljYXRpb24vanNvbjsgY2hhcnNldD11dGYtOCIsIm1lbW9yeSI6NDA5Nn19.WKB14SjgTceKYyhONw2oXTkiOao6X4-UAS7cIuwqGvo&asrc=run_on_apify)
```
import { PlaywrightCrawler } from 'crawlee';  
  
// PlaywrightCrawler crawls the web using a headless browser controlled by the Playwright library.  
const crawler = new PlaywrightCrawler({  
    // Use the requestHandler to process each of the crawled pages.  
    async requestHandler({ request, page, enqueueLinks, pushData, log }) {  
        const title = await page.title();  
        log.info(`Title of ${request.loadedUrl} is '${title}'`);  
  
        // Save results as JSON to `./storage/datasets/default` directory.  
        await pushData({ title, url: request.loadedUrl });  
  
        // Extract links from the current page and add them to the crawling queue.  
        await enqueueLinks();  
    },  
  
    // Uncomment this option to see the browser window.  
    // headless: false,  
  
    // Comment this option to scrape the full website.  
    maxRequestsPerCrawl: 20,  
});  
  
// Add first URL to the queue and start the crawl.  
await crawler.run(['https://crawlee.dev']);  
  
// Export the whole dataset to a single file in `./result.csv`.  
await crawler.exportData('./result.csv');  
  
// Or work with the data directly.  
const data = await crawler.getData();  
console.table(data.items);  

```

Deploy to the cloud ☁️
----------------------

Crawlee is developed by [**Apify**](https://apify.com), the web scraping and automation platform. You can deploy a **Crawlee** project wherever you want (see our deployment guides for [**AWS Lambda**](https://crawlee.dev/docs/deployment/aws-cheerio) and [**Google Cloud**](https://crawlee.dev/docs/deployment/gcp-cheerio)), but using the [**Apify platform**](https://console.apify.com/) will give you the best experience. With a few simple steps, you can convert your **Crawlee** project into a so-called **Actor**. Actors are serverless micro-apps that are easy to develop, run, share, and integrate. The infra, proxies, and storages are ready to go. [Learn more about Actors](https://apify.com/actors).

1️⃣ First, install the **Apify SDK** to your project, as well as the **Apify CLI**. The SDK will help with the Apify integration, while the CLI will help us with the initialization and deployment.

```
npm install apify  
npm install -g apify-cli  

```

2️⃣ The next step is to add `Actor.init()` to the beginning of your main script and `Actor.exit()` to the end of it. This will enable the integration to the Apify Platform, so the [cloud storages](https://apify.com/storage) (e.g. `RequestQueue`) will be used. The code should look like this:

[Run on](https://console.apify.com/actors/6i5QsHBMtm3hKph70?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcbiAgICBcImNvZGVcIjogXCJpbXBvcnQgeyBQbGF5d3JpZ2h0Q3Jhd2xlciB9IGZyb20gJ2NyYXdsZWUnO1xcblxcbi8vIEltcG9ydCB0aGUgYEFjdG9yYCBjbGFzcyBmcm9tIHRoZSBBcGlmeSBTREsuXFxuaW1wb3J0IHsgQWN0b3IgfSBmcm9tICdhcGlmeSc7XFxuXFxuLy8gU2V0IHVwIHRoZSBpbnRlZ3JhdGlvbiB0byBBcGlmeS5cXG5hd2FpdCBBY3Rvci5pbml0KCk7XFxuXFxuLy8gQ3Jhd2xlciBzZXR1cCBmcm9tIHRoZSBwcmV2aW91cyBleGFtcGxlLlxcbmNvbnN0IGNyYXdsZXIgPSBuZXcgUGxheXdyaWdodENyYXdsZXIoe1xcbiAgICAvLyBVc2UgdGhlIHJlcXVlc3RIYW5kbGVyIHRvIHByb2Nlc3MgZWFjaCBvZiB0aGUgY3Jhd2xlZCBwYWdlcy5cXG4gICAgYXN5bmMgcmVxdWVzdEhhbmRsZXIoeyByZXF1ZXN0LCBwYWdlLCBlbnF1ZXVlTGlua3MsIHB1c2hEYXRhLCBsb2cgfSkge1xcbiAgICAgICAgY29uc3QgdGl0bGUgPSBhd2FpdCBwYWdlLnRpdGxlKCk7XFxuICAgICAgICBsb2cuaW5mbyhgVGl0bGUgb2YgJHtyZXF1ZXN0LmxvYWRlZFVybH0gaXMgJyR7dGl0bGV9J2ApO1xcblxcbiAgICAgICAgLy8gU2F2ZSByZXN1bHRzIGFzIEpTT04gdG8gLi9zdG9yYWdlL2RhdGFzZXRzL2RlZmF1bHRcXG4gICAgICAgIGF3YWl0IHB1c2hEYXRhKHsgdGl0bGUsIHVybDogcmVxdWVzdC5sb2FkZWRVcmwgfSk7XFxuXFxuICAgICAgICAvLyBFeHRyYWN0IGxpbmtzIGZyb20gdGhlIGN1cnJlbnQgcGFnZVxcbiAgICAgICAgLy8gYW5kIGFkZCB0aGVtIHRvIHRoZSBjcmF3bGluZyBxdWV1ZS5cXG4gICAgICAgIGF3YWl0IGVucXVldWVMaW5rcygpO1xcbiAgICB9LFxcblxcbiAgICAvLyBVbmNvbW1lbnQgdGhpcyBvcHRpb24gdG8gc2VlIHRoZSBicm93c2VyIHdpbmRvdy5cXG4gICAgLy8gaGVhZGxlc3M6IGZhbHNlLFxcblxcbiAgICAvLyBVbmNvbW1lbnQgdGhpcyBvcHRpb24gdG8gc2NyYXBlIHRoZSBmdWxsIHdlYnNpdGUuXFxuICAgIG1heFJlcXVlc3RzUGVyQ3Jhd2w6IDIwLFxcbn0pO1xcblxcbi8vIEFkZCBmaXJzdCBVUkwgdG8gdGhlIHF1ZXVlIGFuZCBzdGFydCB0aGUgY3Jhd2wuXFxuYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pO1xcblxcbi8vIEV4cG9ydCB0aGUgZW50aXJldHkgb2YgdGhlIGRhdGFzZXQgdG8gYSBzaW5nbGUgZmlsZSBpblxcbi8vIC4vc3RvcmFnZS9rZXlfdmFsdWVfc3RvcmVzL3Jlc3VsdC5jc3ZcXG5jb25zdCBkYXRhc2V0ID0gYXdhaXQgY3Jhd2xlci5nZXREYXRhc2V0KCk7XFxuYXdhaXQgZGF0YXNldC5leHBvcnRUb0NTVigncmVzdWx0Jyk7XFxuXFxuLy8gT3Igd29yayB3aXRoIHRoZSBkYXRhIGRpcmVjdGx5LlxcbmNvbnN0IGRhdGEgPSBhd2FpdCBjcmF3bGVyLmdldERhdGEoKTtcXG5jb25zb2xlLmxvZyhkYXRhLml0ZW1zLnNsaWNlKDAsIDUpKTtcXG5cXG4vLyBPbmNlIGZpbmlzaGVkLCBjbGVhbiB1cCB0aGUgZW52aXJvbm1lbnQuXFxuYXdhaXQgQWN0b3IuZXhpdCgpO1xcblwiXG59Iiwib3B0aW9ucyI6eyJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjQwOTZ9fQ.Te7qi0ocWNsH3ujFkgIv8AO9GQ5Wk4DZeQ9-zHTy7Vo&asrc=run_on_apify)
```
import { PlaywrightCrawler, Dataset } from 'crawlee';  
  
// Import the `Actor` class from the Apify SDK.  
import { Actor } from 'apify';  
  
// Set up the integration to Apify.  
await Actor.init();  
  
// Crawler setup from the previous example.  
const crawler = new PlaywrightCrawler({  
    // ...  
});  
await crawler.run(['https://crawlee.dev']);  
  
// Once finished, clean up the environment.  
await Actor.exit();  

```

3️⃣ Then you will need to [sign up for the Apify account](https://console.apify.com/sign-up). Once you have it, use the Apify CLI to log in via `apify login`. The last two steps also involve the Apify CLI. Call the `apify init` first, which will add Apify config to your project, and finally run the `apify push` to deploy it.

```
apify login # so the CLI knows you  
apify init  # and the Apify platform understands your project  
apify push  # time to ship it!  

```
Docs

* [Guides](/docs/guides)
* [Examples](/docs/examples)
* [API reference](/api/core)
* [Upgrading to v3](/docs/upgrading/upgrading-to-v3)
Community

* [Blog](/blog)
* [Discord](https://discord.com/invite/jyEM2PRvMU)
* [Stack Overflow](https://stackoverflow.com/questions/tagged/crawlee)
* [Twitter](https://twitter.com/apify)
More

* [Apify Platform](https://apify.com)
* [Docusaurus](https://docusaurus.io)
* [GitHub](https://github.com/apify/crawlee)
Crawlee is free and open sourceBuilt by


