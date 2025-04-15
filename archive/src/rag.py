from langchain_huggingface import HuggingFaceEmbeddings  # noqa: F401

from langchain_core.embeddings.embeddings import Embeddings

from transformers import AutoTokenizer, AutoModel  # noqa: F401
import torch
import torch.nn.functional as F
import warnings
warnings.filterwarnings("ignore", message="To copy construct from a tensor, it is recommended to use sourceTensor.clone().detach()")

class CustomEmbeddingModel(Embeddings):
    def __init__(self):
        self.model = AutoModel.from_pretrained('nvidia/NV-Embed-v2', trust_remote_code=True, device_map='auto')

        self.max_length = 32768
        self.model.tokenizer.padding_side = 'right'
        self.batch_size = 1
        
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i+self.batch_size]
            with torch.no_grad():
                e = self.model.encode(batch_texts, instruction='', max_length=self.max_length)
                e = F.normalize(e, p=2, dim=1)
                embeddings.extend(e.cpu().numpy())
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        with torch.no_grad():
            embedding = self.model.encode([text], instruction='', max_length=self.max_length)
            embedding = F.normalize(embedding, p=2, dim=1)
        return embedding.cpu().numpy()[0]
    

# # model_name = "nvidia/NV-Embed-v2"
# model_name = 'sentence-transformers/all-mpnet-base-v2'
# model_kwargs = {'device': 'cuda', 'trust_remote_code': True}
# encode_kwargs = {'normalize_embeddings': True}
# embeddings = HuggingFaceEmbeddings(
#     model_name=model_name,
#     model_kwargs=model_kwargs,
#     encode_kwargs=encode_kwargs
# )
embeddings = CustomEmbeddingModel()

from langchain_core.vectorstores import InMemoryVectorStore
vector_store = InMemoryVectorStore(embeddings)

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)



import asyncio

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from markdownify import markdownify as md

docs = []

async def main() -> None:
    crawler = BeautifulSoupCrawler(
        # Limit the crawl to max requests. Remove or increase it for crawling all links.
        max_requests_per_crawl=1,
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
        
        
        docs.extend(text_splitter.split_documents([Document(page_content=data['markdown'])]))
        

        # Push the extracted data to the default dataset.
        await context.push_data(data)

        # Enqueue all links found on the page.
        await context.enqueue_links()

    # Run the crawler with the initial list of URLs.
    await crawler.run(['https://crawlee.dev'])
    await crawler.export_data_json('crawlee_data.json')
    data = await crawler.get_data()
    # crawler.log.info(f'Extracted data: {data.items}')
    
    # save markdown 0 to test.md
    # save markdown 0 to test.md
    with open('test.md', 'w') as f:
        f.write(data.items[0]['markdown'])

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
    print(len(docs))
    
    warnings.filterwarnings("ignore", message="To copy construct from a tensor")
    
    vector = embeddings.embed_query("What is web scraping?")
    print(vector)
    _ = vector_store.add_documents(docs)
    retrieved_docs = vector_store.similarity_search_by_vector(vector, 1)
    print(retrieved_docs)
