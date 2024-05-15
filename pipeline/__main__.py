from typing import Any, Dict
from . import Pipeline, PipelineJob
import requests
from bs4 import BeautifulSoup
from typing import List
from dataclasses import dataclass

def cook_soup(url):
    res = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        )
    if not res.ok:
        return None
    return BeautifulSoup(res.content)

def find_all_image_page_links(soup: BeautifulSoup) -> List[str]:
    links = []
    for link in soup.find_all("a"):
        if link.img is not None:
            links.append(link.get("href"))
    if len(links) == 0:
        raise Exception("No links found")
    return links


def get_bunkrr_links(soup: BeautifulSoup) -> List[str]:
    gallery_div = soup.find("div", class_="lightgallery")
    if gallery_div is None:
        video = soup.find("video")
        if video is None: 
            raise Exception("No image or video found")
        return [video.source.get("src")]
    return [gallery_div.img.get("src")]


class PageSearcher(PipelineJob):

    def __init__(self):
        super().__init__('PageSearcher')

    def run(self, **kwargs) -> Dict[str, Any]:
        url = kwargs.get('url')
        soup = cook_soup(url)
        links = find_all_image_page_links(soup)
        self.set_state('searchUrls', links)
        for l in links:
            self.push_message('search_urls', l)
        return {
            'urls': links
        }
    
class ImageSearcher(PipelineJob):

    def __init__(self):
        super().__init__('ImageSeracher')

    def run(self, **kwargs) -> Dict[str, Any]:
        urls = kwargs.get('urls')
        from time import sleep
        file_links = []
        for url in urls[:10]:
            soup = cook_soup(url)
            try:
                file_links.extend(get_bunkrr_links(soup))
            except:
                print(f"Url {url} failed to fetch")
                self.push_message('search_urls', url)
                self.update_state('failedUrls', lambda l: l.append(url) if isinstance(l, list) else [l])
        self.set_state('fileUrls', file_links)
        for l in file_links:
            self.push_message('file_urls', l)
        return {
            'imageUrls': file_links
        }   
        
p = Pipeline()
p.prepare([
    PageSearcher(),
    ImageSearcher()
])
p.run(url='https://bunkrrr.org/a/WhtHumYC')