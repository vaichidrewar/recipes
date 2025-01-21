import scrapy
import re
import newspaper

class NewsSpider(scrapy.Spider):
    name = 'recipes'
    allowed_domains = ['nishamadhulika.com']
    start_urls = ['https://nishamadhulika.com/en/']  # Replace with your target URLs

    def parse(self, response):
        self.logger.info(f'Parsing page: {response.url}')
        recipe_pattern = r'/en/\d+-[\w_]+\.html$'
        category_pattern = r'/en/category/\d+-[\w-]+\.html(?:/\d+)?$'
        
        links_found = 0
        recipes_found = 0
        categories_found = 0
        
        for href in response.css('a::attr(href)'):
            links_found += 1
            link = href.get()
            if not link:
                self.logger.debug(f'Skipping empty link')
                continue
            
            if re.search(recipe_pattern, link):
                recipes_found += 1
                self.logger.info(f'Found recipe URL ({recipes_found}): {link}')
                yield response.follow(href, self.parse_article)
            elif re.search(category_pattern, link):
                categories_found += 1
                self.logger.info(f'Found category URL ({categories_found}): {link}')
                yield response.follow(href, self.parse)
            else:
                self.logger.debug(f'URL did not match any patterns: {link}')
        
        self.logger.info(f'Page {response.url} summary:')
        self.logger.info(f'  Total links found: {links_found}')
        self.logger.info(f'  Recipe links found: {recipes_found}')
        self.logger.info(f'  Category links found: {categories_found}')

    def parse_article(self, response):
        self.logger.info(f'Parsing recipe: {response.url}')
        # Use Newspaper4k to parse the article
        article = newspaper.article(response.url, language='en', input_html=response.text)
        article.parse()
        article.nlp()

        # Extracted information
        # Extract all available fields
        data = {
            "url": response.url,
            "read_more_link": article.read_more_link,
            "language": article.meta_lang or 'en',
            "title": article.title,
            "top_image": article.top_image,
            "meta_img": article.meta_img,
            "images": article.images,
            "movies": article.movies,
            "keywords": article.keywords,
            "meta_keywords": article.meta_keywords,
            "tags": list(article.tags) if article.tags else None,
            "authors": article.authors,
            "publish_date": article.publish_date.isoformat() if article.publish_date else None,
            "summary": article.summary,
            "meta_description": article.meta_description,
            "meta_lang": article.meta_lang,
            "meta_favicon": article.meta_favicon,
            "meta_site_name": article.meta_site_name,
            "canonical_link": article.canonical_link,
            "text": article.text
        }
        if data["text"] or data["title"]:
            self.logger.info(f"Successfully scraped recipe: {response.url}")
            self.logger.debug(f"Recipe data: {data}")
            yield data
        else:
            self.logger.warning(f"No content found for recipe: {response.url}")        
