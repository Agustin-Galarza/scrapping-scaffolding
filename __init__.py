from io import TextIOWrapper
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List, Callable, Optional
import concurrent.futures
import requests
import time
from bs4 import BeautifulSoup
import json
from pathlib import Path

from utils import NamedResource, ShowsProgress, check_response


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
    def __init__(self, *args, **kwargs):
        try:
            super(ScrappingJob, self).__init__(**kwargs)
        except TypeError:
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

    @abstractmethod
    def on_exit(self, log_file: Optional[TextIOWrapper]) -> None:
        pass


class URLScrapper(ScrappingJob, ShowsProgress, NamedResource):
    __DEFAULT_NAME = "ScrappingJob"

    def __init__(self, job: Callable[[str], List[str]], *args, **kwargs):
        """
        job: function that receives an html text and extratc a list of urls
        """
        kwargs.setdefault("name", self.__DEFAULT_NAME)
        super(URLScrapper, self).__init__(**kwargs)
        self.base_description = kwargs.get("description", "Scrapping urls")
        # Stats
        self.save_stats = kwargs.get("save_stats", False)
        self.stats_filepath: Optional[str] = kwargs.get("stats_filepath", None)
        self.stats = dict(tries=0, fails=0, urls=[])
        # Job
        self.job = job

    # Name
    def has_default_name(self) -> bool:
        return super().get_name() == self.__DEFAULT_NAME

    #########################

    # Stats
    def __add_stat(self, url: str, success: bool):
        if not self.save_stats:
            return
        self.stats["tries"] += 1
        self.stats["fails"] += 1 if not success else 0
        self.stats["urls"].append(dict(value=url, processed=success))

    def __save_stats(self):
        if not self.save_stats:
            return
        path = (
            self.stats_filepath
            if self.stats_filepath is not None
            else f"./{self.name}-stats.log"
        )
        with open(path, "w+") as file:
            json.dump(self.stats, file)

    ########################

    def get_urls(self, url: str, info: ScrappingInfo) -> Optional[List[str]]:
        try:
            super().advance_progress()

            response = requests.get(
                url,
                timeout=info.request_timeout,
                headers=info.request_headers,
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
                res = self.get_urls(url, info)
                if res is not None:
                    self.__add_stat(url, True)
                    output_links.extend(res)
                else:
                    self.__add_stat(url, False)
            self.found_len = len(output_links)
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
                self.__add_stat(url, False)
            else:
                if data is not None:
                    self.__add_stat(url, True)
                    output_links.extend(data)
                else:
                    self.__add_stat(url, False)

        super().clear_progress_bar()
        self.found_len = len(output_links)
        return output_links

    def on_exit(self, log_file: Optional[TextIOWrapper]) -> None:
        tries = self.stats["tries"]
        fails = self.stats["fails"]
        successes = tries - fails
        super().print_statement(
            f"Scanned {tries} pages, failed to get {fails}",
            log_file,
        )
        super().print_statement(f"{self.found_len} links found", log_file)
        self.__save_stats()


class URLProcessor(ScrappingJob, NamedResource):
    __DEFAULT_NAME = "URLProcessor"

    def __init__(
        self, processor: Callable[[List[str]], None], async_=False, *args, **kwargs
    ):
        kwargs.setdefault("name", self.__DEFAULT_NAME)
        super(URLProcessor, self).__init__(**kwargs)
        self.processor = processor
        self.async_ = async_

    # Name
    def has_default_name(self) -> bool:
        return super().get_name() == self.__DEFAULT_NAME

    #####################

    def execute(self, urls: List[str], info: ScrappingInfo):
        if not self.async_:
            try:
                super().print_statement("Processing urls...", info.log_file)
                self.processor(urls)
            except Exception as e:
                super().print_statement(
                    f"Error while processing files: {e}", info.log_file
                )
            return urls

        super().print_statement(
            "Error: async not implemented, skipping job", info.log_file
        )
        return urls

    def on_exit(self, log_file: Optional[TextIOWrapper]) -> None:
        pass


class FileDownloader(ScrappingJob, ShowsProgress, NamedResource):
    __DEFAULT_NAME = "FileDownloader"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("name", self.__DEFAULT_NAME)
        super(FileDownloader, self).__init__(**kwargs)
        self.directory = kwargs.get("dir", "./")
        self.base_name = kwargs.get("basename", "file")
        self.base_description = kwargs.get("description", "Downloading files")
        self.file_download_timeout = kwargs.get("file_timeout", 40)
        # Stats
        self.save_stats = kwargs.get("save_stats", False)
        self.stats_filepath: Optional[str] = kwargs.get("stats_filepath", None)
        self.append_files = kwargs.get("append_files", True)
        self.stats = dict(tries=0, fails=0, urls=[])

    # Name
    def has_default_name(self) -> bool:
        return super().get_name() == self.__DEFAULT_NAME

    ####################

    # Stats
    def __add_stat(self, url: str, success: bool):
        if not self.save_stats:
            return
        self.stats["tries"] += 1
        self.stats["fails"] += 1 if not success else 0
        self.stats["urls"].append(dict(value=url, processed=success))

    def __save_stats(self):
        if not self.save_stats:
            return
        path = (
            self.stats_filepath
            if self.stats_filepath is not None
            else f"./{self.name}-stats.log"
        )
        with open(path, "w+") as file:
            json.dump(self.stats, file)

    ############################

    def __download_image(self, url: str, path: str, info: ScrappingInfo):
        try:
            super().advance_progress()
            response = requests.get(
                url, timeout=self.file_download_timeout, headers=info.request_headers
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

            index_offset = 0

            for index, image in enumerate(urls):
                image_name = f"{self.base_name}-{index+index_offset:04d}.jpg"
                image_path = self.directory + image_name
                while self.append_files and Path(image_path).exists():
                    index_offset += 1
                    image_name = f"{self.base_name}-{index+index_offset:04d}.jpg"
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
                self.__add_stat(url, True)
            except Exception as ex:
                super().log_statement(
                    f"Could not download image for {url}: {ex}", info.log_file
                )
                self.__add_stat(url, False)

    def on_exit(self, log_file: Optional[TextIOWrapper]) -> None:
        super().clear_progress_bar()
        super().print_statement(
            f"Tried to download {super().get_tries()} images, failed to download {super().get_fails()}",
            log_file,
        )
        self.__save_stats()


class Scrapper:
    def __init__(self, job_sequence: List[ScrappingJob], *args, **kwargs):
        self.job_sequence = job_sequence
        self.__check_jobs()
        log_filepaht = kwargs.get("log_file", None)
        self.scrapping_info = ScrappingInfo(
            html_parser="html.parser",
            base_url=kwargs.get("base_url", ""),
            sparse_requests=kwargs.get("sparse_requests", False),
            request_cooldown=kwargs.get("request_cooldown", 0),
            request_timeout=kwargs.get("request_timeout", 10),
            max_workers=kwargs.get("max_workers", 1),
            log_file=open(log_filepaht, "w+") if log_filepaht is not None else None,
            request_headers=kwargs.get("request_headers", {}),
        )

    def __check_jobs(self):
        for index, job in enumerate(self.job_sequence):
            if job.has_default_name():
                job.set_name(f"Job {index} - {job.__class__.__name__}")

    def run(self, urls: List[str]):
        to_process = urls

        for job in self.job_sequence:
            to_process = job.execute(to_process, self.scrapping_info)
            job.on_exit(self.scrapping_info.log_file)

        if self.scrapping_info.log_file is not None:
            self.scrapping_info.log_file.close()
        return to_process
