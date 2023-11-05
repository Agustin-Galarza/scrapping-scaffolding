from abc import ABC, abstractmethod
from io import TextIOWrapper
from typing import List, Callable, Optional
import concurrent.futures
from dataclasses import dataclass
import requests
import time
from utils import ShowsProgress
from bs4 import BeautifulSoup


def check_response(response):
    if not response.ok:
        raise Exception(f"Error on request, obtained: {response.status_code}")


@dataclass
class ScrappingInfo:
    html_parser: str
    base_url: str
    sparse_requests: bool
    request_cooldown: float
    request_timeout: float
    max_workers: int
    log_file: Optional[TextIOWrapper]
    request_headers: dict


class ScrappingJob(ABC):
    def __init__(self):
        super(ScrappingJob, self).__init__()

    def print_statement(self, msg: str, file: Optional[TextIOWrapper]):
        if file is not None:
            print(msg, file=file, flush=True)
        print(msg, flush=True)

    def log_statement(self, msg: str, file: Optional[TextIOWrapper]):
        if file is not None:
            print(msg, file=file)

    @abstractmethod
    def execute(self, urls: List[str], info: ScrappingInfo):
        pass


class URLScrapper(ScrappingJob, ShowsProgress):
    def __init__(self, job: Callable[[str], List[str]], *args, **kwargs):
        """
        job: function that receives an html text and extratc a list of urls
        """
        super(URLScrapper, self).__init__()
        self.base_description = kwargs.get("description", "Scrapping urls")
        self.job = job

    def get_urls(self, url: str, info: ScrappingInfo) -> Optional[List[str]]:
        try:
            super().advance_progress()

            response = requests.get(
                url, timeout=info.request_timeout, headers=info.request_headers
            )
            check_response(response)

            # TODO: orchestrate waits for requests
            if info.sparse_requests:
                time.sleep(info.request_cooldown)

            page_soup = BeautifulSoup(response.text, info.html_parser)
            urls = self.job(page_soup)

            def complete_url(u: str) -> str:
                return (info.base_url + u) if not u.startswith("http") else u

            return list(map(complete_url, urls))
        except Exception as e:
            super().add_fail()
            super().log_statement(f"Failed job for {url}: {e}", info.log_file)
            return None

    def execute(self, urls: List[str], info: ScrappingInfo):
        output_links = []
        future_to_url = {}
        super().init_progress_bar(len(urls), self.base_description)

        if len(urls) < 10:
            for url in urls:
                super().advance_progress()
                output_links.extend(self.get_urls(url, info))
            return output_links

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=info.max_workers
        ) as executor:
            for url in urls:
                try:
                    future_to_url.update(
                        {executor.submit(self.get_urls, url, info): url}
                    )
                except Exception:
                    super().add_fail()

        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]

            try:
                data: Optional[List[str]] = future.result()
            except Exception as e:
                super().log_statement(
                    f"Could not search in url {url}: {e}", info.log_file
                )
            else:
                if data is not None:
                    output_links.extend(data)

        super().clear_progress_bar()
        super().print_statement(
            f"Scanned {super().get_tries()} pages, failed to get {super().get_fails()}",
            info.log_file,
        )
        super().print_statement(f"{len(output_links)} links found", info.log_file)
        return output_links


class FileDownloader(ScrappingJob, ShowsProgress):
    def __init__(self, *args, **kwargs):
        super(FileDownloader, self).__init__()
        self.directory = kwargs.get("dir", "./")
        self.base_name = kwargs.get("basename", "image")
        self.base_description = kwargs.get("description", "Downloading images")
        self.image_download_timeout = kwargs.get("image_timeout", 40)

    def __download_image(self, url: str, path: str, info: ScrappingInfo):
        try:
            super().advance_progress()
            response = requests.get(
                url, timeout=self.image_download_timeout, headers=info.request_headers
            )
            check_response(response)

            if info.sparse_requests:
                time.sleep(info.request_cooldown)

            with open(path, "wb") as f:
                # TODO: identify file extension and download accordingly
                f.write(response.content)
        except Exception as ex:
            super().log_statement(ex, info.log_file)
            super().add_fail()
            return False
        else:
            return True

    def execute(self, urls: List[str], info: ScrappingInfo):
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=info.max_workers
        ) as executor:
            future_to_url = {}

            super().print_statement(f"Fetching {len(urls)} files", info.log_file)
            super().init_progress_bar(len(urls), self.base_description)

            for index, image in enumerate(urls):
                image_name = f"{self.base_name}-{index:04d}.jpg"
                image_path = self.directory + image_name

                future_to_url.update(
                    {
                        executor.submit(
                            self.__download_image, image, image_path, info
                        ): image
                    }
                )

        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception as ex:
                super().log_statement(
                    f"Could not download image for {url}: {ex}", info.log_file
                )

        super().clear_progress_bar()
        super().print_statement(
            f"Tried to download {super().get_tries()} images, failed to download {super().get_fails()}",
            info.log_file,
        )


class Scrapper:
    def __init__(self, job_sequence: List[ScrappingJob]):
        self.job_sequence = job_sequence
