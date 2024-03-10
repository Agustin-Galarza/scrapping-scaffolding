from __init__ import Scrapper, FileDownloader, URLScrapper, URLProcessor
from bs4 import BeautifulSoup
from typing import List
from functools import partial
from pathlib import Path
import json

WILLOW_URLS = [
    "https://bunkrr.su/a/0hKWIdTx",
    "https://bunkrr.su/a/Zd5yMmUk",
    "https://bunkrr.su/a/iWiXbGCB",
]


def load_list(path):
    values = []
    with open(path, "r+") as file:
        for line in file:
            values.append(line.rstrip())
    return values


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


def write_list(urls: List[str], filepath: Path) -> None:
    with open(filepath, "w+") as file:
        for url in urls:
            file.write(url + "\n")


def load_failed(previous: List[str], path: Path):
    with open(path) as file:
        stats: dict = json.load(file)
        failed = previous
        for url in stats["urls"]:
            if not url["processed"]:
                failed.append(url["value"])
        return failed


def get_willow_pages(soup: BeautifulSoup) -> List[str]:
    pages = []
    for link in soup.find_all("a"):
        if (
            link.img is not None
            and len(link.img.get("class")) > 0
            and link.img.get("class")[0].startswith("thumbnail")
        ):
            pages.append(link.get("href"))
    if len(pages) == 0:
        raise Exception("No pages found")
    return pages


def get_willow_links(soup: BeautifulSoup) -> List[str]:
    for link in soup.find_all("a"):
        if link.get("href").endswith(".jpg"):
            return [link.get("href")]
    return None


def get_willow_pics():
    urls = [f"https://faponic.com/willowsdreaming/{i}" for i in range(202)]

    Scrapper(
        [
            # URLScrapper(
            #     get_willow_pages,
            #     description="Fetching pages",
            #     save_stats=True,
            #     name="Find pages",
            #     stats_filepath="output/willow-pages-stats",
            # ),
            URLScrapper(
                get_willow_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath="output/willow-images-stats",
            ),
            FileDownloader(
                dir="./output/images/",
                file_timeout=120,
                name="Download images",
                basename="image",
                save_stats=True,
                stats_filepath="output/willow-download-stats",
            ),
        ],
        base_url="https://faponic.com",
        sparse_requests=False,
        request_cooldown=0.1,
        request_timeout=10,
        log_file="./test.willow.log",
        request_headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        max_workers=16,
    ).run(urls)


def retry_for_failures(output_folder='output/'):
    print("\n-------------------------------------------------------------------------------------------------------\n")
    scrapper = Scrapper(
        [
            URLProcessor(partial(load_failed, path=Path(f"{output_folder}/images-stats"))),
            URLScrapper(
                get_bunkrr_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath="output/images-stats-retry",
            ),
            URLProcessor(partial(load_failed, path=Path(f"{output_folder}/download-stats"))),
            FileDownloader(
                dir=f"{output_folder}/images/",
                file_timeout=120,
                name="Download images",
                basename="image",
                stats_filepath="output/download-stats-retry",
                append_files=True,
            ),
        ],
        base_url="https://bunkrr.su",
        sparse_requests=False,
        request_cooldown=0.1,
        request_timeout=10,
        log_file="./test.log",
        request_headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        max_workers=16,
    )

    scrapper.run([])


def main(output_folder = 'output/', url = None):
    urls = ["https://bunkr.sk/a/4W0sH4Jc"] if url is None else [url]

    if not Path(output_folder).exists():
        Path(output_folder).mkdir()
    if not Path(f"{output_folder}/images").exists():
        Path(f"{output_folder}/images").mkdir()

    scrapper = Scrapper(
        [
            URLScrapper(
                find_all_image_page_links,
                description="Fetching pages",
                save_stats=True,
                name="Find pages",
                stats_filepath=f"{output_folder}/pages-stats",
            ),
            # URLProcessor(write_page_links),
            URLScrapper(
                get_bunkrr_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath=f"{output_folder}/images-stats",
            ),
            # URLProcessor(write_image_links),
            FileDownloader(
                dir=f"./{output_folder}/images/",
                file_timeout=120,
                name="Download images",
                basename="image",
                save_stats=True,
                stats_filepath=f"{output_folder}/download-stats",
            ),
        ],
        base_url="https://bunkrr.su",
        sparse_requests=False,
        request_cooldown=0.1,
        request_timeout=10,
        log_file="./output/test.log",
        request_headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        max_workers=16,
    )


    scrapper.run(urls)

if __name__ == "__main__":
    output_folder = "output/"
    url = 'https://bunkr.sk/a/rU0U5eAl'
    main(output_folder, url)
    retry_for_failures(output_folder)
