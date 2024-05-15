from scrapper import Scrapper, FileDownloader, URLScrapper, URLProcessor
from bs4 import BeautifulSoup
from typing import List, Optional
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


def retry_for_failures(output_folder='output/'):
    print("\n-------------------------------------------------------------------------------------------------------\n")
    scrapper = Scrapper(
        [
            URLProcessor(partial(load_failed, path=Path(f"{output_folder}/images-stats.json"))),
            URLScrapper(
                get_bunkrr_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath=f"{output_folder}/images-stats-retry.json",
            ),
            URLProcessor(partial(load_failed, path=Path(f"{output_folder}/download-stats.json"))),
            FileDownloader(
                dir=f"{output_folder}/images/",
                file_timeout=120,
                name="Download images",
                basename="image",
                stats_filepath=f"{output_folder}/download-stats-retry.json",
                save_stats=True,
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


def main(output_folder = 'output/', output_name: Optional[str] = None, identifier: Optional[str] = None, url = None):
    urls = ["https://bunkr.sk/a/4W0sH4Jc"] if url is None else [url]

    scrapper_name = 'scrapper'
    if output_name is not None:
        output_folder = Path.joinpath(Path(output_folder), output_name)
        scrapper_name = output_name
    if not Path(output_folder).exists():
        Path(output_folder).mkdir()
    if not Path(f"{output_folder}/images").exists():
        Path(f"{output_folder}/images").mkdir()

    if identifier is not None:
        scrapper_name += f" - {identifier}"

    scrapper = Scrapper(
        [
            URLScrapper(
                find_all_image_page_links,
                description="Fetching pages",
                save_stats=True,
                name="Find pages",
                stats_filepath=f"{output_folder}/pages-stats.json",
            ),
            # URLProcessor(write_page_links),
            URLScrapper(
                get_bunkrr_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath=f"{output_folder}/images-stats.json",
            ),
            # URLProcessor(write_image_links),
            FileDownloader(
                dir=f"./{output_folder}/images/",
                file_timeout=120,
                name="Download images",
                basename="image",
                save_stats=True,
                stats_filepath=f"{output_folder}/download-stats.json",
            ),
            FileDownloader(
                dir=f"./{output_folder}/images/",
                file_timeout=120,
                name="Retry failures",
                basename="image",
                save_stats=True,
                append_files=True,
                stats_filepath=f"{output_folder}/retry-stats.json",
            ),
        ],
        name=scrapper_name,
        base_url="https://bunkrr.su",
        sparse_requests=True,
        request_cooldown=0.3,
        request_timeout=10,
        log_path="./output",
        request_headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        max_workers=16,
    )
    scrapper.run(urls)

if __name__ == "__main__":
    output_folder = "output"
    album = "Toph"
    url = 'https://bunkrrr.org/a/WhtHumYC'
    # https://bunkr.sk/a/9mou5a5O
    main(output_folder=output_folder, output_name=album, url=url)
    # retry_for_failures(output_folder)
