from bs4 import BeautifulSoup
from typing import List, Union, Optional
from pathlib import Path
from scrapper import Scrapper, URLScrapper, FileDownloader


def __find_all_image_page_links(soup: BeautifulSoup) -> List[str]:
    links = []
    for link in soup.find_all("a"):
        if link.img is not None:
            links.append(link.get("href"))
    if len(links) == 0:
        raise Exception("No links found")
    return links


def __get_bunkrr_links(soup: BeautifulSoup) -> List[str]:
    gallery_div = soup.find("div", class_="lightgallery")
    if gallery_div is None:
        video = soup.find("video")
        if video is None: 
            raise Exception("No image or video found")
        return [video.source.get("src")]
    return [gallery_div.img.get("src")]


def prepare_bunkr_scrapper(name: str, output_path: Path, content_path: Optional[Path]) -> Scrapper:
    content_download_path = output_path.joinpath(content_path) if content_path is not None else output_path
    content_download_path.mkdir(parents=True,exist_ok=True)

    return Scrapper(
        [
            URLScrapper(
                __find_all_image_page_links,
                description="Fetching pages",
                save_stats=True,
                name="Find pages",
                stats_filepath=f"{output_path}/pages-stats.json",
            ),
            # URLProcessor(write_page_links),
            URLScrapper(
                __get_bunkrr_links,
                description="Fetching image links",
                save_stats=True,
                name="Find images",
                stats_filepath=f"{output_path}/images-stats.json",
            ),
            # URLProcessor(write_image_links),
            FileDownloader(
                dir=f"{content_download_path}",
                file_timeout=120,
                name="Download images",
                basename="image",
                save_stats=True,
                stats_filepath=f"{output_path}/download-stats.json",
            ),
        ],
        name=name,
        base_url="https://bunkrr.su",
        sparse_requests=False,
        request_cooldown=0.2,
        request_timeout=10,
        log_path=output_path,
        request_headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        max_workers=16,
    )