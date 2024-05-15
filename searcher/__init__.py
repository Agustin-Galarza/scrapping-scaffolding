from bs4 import BeautifulSoup, Tag
from typing import List, Set, Iterable, Optional, Dict, Union
from pathlib import Path
import json
import requests
from dataclasses import dataclass, asdict
from io_utils.json import JSONable, JSONableDataclass
from typing_extensions import Self
from searcher.download.bunkr import prepare_bunkr_scrapper
import re

from .utils import parse_download_name, parse_size_name, parse_size_bytes

@dataclass
class Config:
    downloads: Path = Path('./output')

def load_config(config_path: Path) -> Config:
    with config_path.open('r') as file:
        c = json.load(file)
        return Config(
            downloads=Path(c['downloads'])
        )

@dataclass
class DownloadInfo(JSONableDataclass):
    album_name: str

@dataclass
class LinkInfo(JSONableDataclass):
    name: str
    url: str

    def get_album_name(self) -> str:
        return f'{self.name.replace(" Clips/GIFs", "").replace(" Clips", "")}'
    
    def to_json(self, destination_file: Union[str,Path]) -> None:
        with open(destination_file, '+w') as file:
            json.dump(asdict(self), file)

    def to_json_str(self) -> str:
        return json.dumps(asdict(self))
    
    def __hash__(self) -> int:
        return hash(f'{self.name} {self.url}')

    def __str__(self) -> str:
        return f'({self.name}: {self.url})'

@dataclass
class AlbumInfo(JSONableDataclass):
    name: str
    url: str
    files: int
    size: str
    downloaded: bool

    def get_size_bytes(self, format='kibi') -> int:
        if format != 'kibi' and format != 'kilo':
            raise Exception(f'Unrecognized format {format}. Accepted values are "kibi" (1 KB = 1024 B) and "kilo" (1 KB = 1000 B)')
        units = {"B": dict(kibi=1,kilo=1), "KB": dict(kibi=2**10,kilo=10**3), "MB": dict(kibi=2**20, kilo=10**6), "GB": dict(kibi=2**30, kil=10**9), "TB": dict(kibi=2**40, kilo=10**12)}

        number, unit = [string.strip() for string in self.size.split()]
        return int(float(number)*units[unit][format])

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self) -> str:
        return f"""
Album
name: {self.name}
url: {self.url}
files: {self.files}
size: {self.size}
downloaded: {self.downloaded}        
"""
    
    def short_str(self) -> str:
        return f"{self.name} || {self.url} || {self.size} || {'Not ' if not self.downloaded else ' '}Downloaded"


def save_downloaded(downloaded: List[str], downloaded_path = 'output/downloaded.json') -> None:
    with open(downloaded_path, '+w') as file:
        json.dump(downloaded, file)


def get_downloaded(downloaded_path = 'output/downloaded.json') -> List[str]:
    with open(downloaded_path, '+r') as file:
        downloaded_list = json.load(file)
        return downloaded_list

def cook_soup(url: str) -> BeautifulSoup:
    res = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        }
        )
    if not res.ok:
        raise Exception(f'Response returned error status {res.status_code}: {res.text}')
    return BeautifulSoup(res.text, 'html.parser')


class BunkrSearch(JSONable):
    query: str
    results: List[AlbumInfo]
    pages: int

    def __init__(self, query: str, results: List[AlbumInfo], results_amount: int, pages: Dict[int, Optional[Iterable[LinkInfo]]]) -> None:
        self.query = query
        self.results = results
        self.__results_len = results_amount
        self.__pages = pages

        self.pages = max(self.__pages.keys())
        
    def __str__(self) -> str:
        res = "\n".join(["\t\t" + r.short_str() for r in self.results])
        return f"""
Search Result for {self.query}:
\talbums found: {self.__results_len}
\ttotal pages: {self.pages}
\tresults:
{res}

Total Size: {parse_size_bytes(sum([r.get_size_bytes() for r in self.results]))}
"""


class BunkrSearcher:

    def __init__(self, config: Config) -> None:
        self.config = config
        self.search_history: List[BunkrSearch] = []
        self.downloads: List[DownloadInfo] = self.__load_downloads()

    def search(self, query: str, save: bool = True, max_loaded_pages: int = 1) -> BunkrSearch:
        soup = cook_soup(self.__build_url(query))

        pages_amount = self.__get_pages_amount(soup)
        pages: Dict[int, Optional[Iterable[LinkInfo]]] = {n: None for n in range(1, pages_amount+1)}
        links = self.__get_result_links(soup)
        pages[1] = links if links != [] else None

        if max_loaded_pages > 1:
            for page in range(2, max_loaded_pages+1):
                l = self.__get_result_links(cook_soup(self.__build_url(query, page)))
                pages[page] = l if l != [] else None
        
        results: List[AlbumInfo] = []
        results_len = 0
        for page, link_list in pages.items():
            if link_list is None:
                continue
            
            for link in link_list:
                info: AlbumInfo = self.__get_album_info(link.url)
                results.append(info)
                results_len += 1

        search = BunkrSearch(
            query,
            results,
            results_len,
            pages
            )
        if save:
            self.search_history.append(search)
        return search

    def __is_downloaded(self, name: str) -> bool:
        for d in self.downloads:
            if d.album_name == parse_download_name(name):
                return True
        return False

    def __load_downloads(self) -> List[DownloadInfo]:
        if not self.config.downloads.exists():
            return []
        downloads = []
        for item in self.config.downloads.iterdir():
            if item.is_dir():
                downloads.append(DownloadInfo(
                    album_name=parse_download_name(item.name)
                ))
        return downloads

    def __get_album_info(self, url: str) -> AlbumInfo:
        soup = cook_soup(url)
        header_div = soup.find('div', class_='mb-12-xxx')
        if header_div is None:
            raise Exception('Header div not found for album', url)
        
        title = header_div.find('h1').string.strip()
        span_items = [i.replace('\n', '').replace('\t','') for i in str(header_div.find('span').string).split(' ', 1)]
        return AlbumInfo(
            name=title,
            url=url,
            files=int(span_items[0].replace('files', '')),
            size=span_items[1].strip('()'),
            downloaded=self.__is_downloaded(title)
        )

    def __is_album_link(tag: Tag) -> bool:
        return tag.name == 'a' and tag.string != 'Visit'

    def __get_result_links(self, soup: BeautifulSoup) -> Iterable[LinkInfo]:
        return [LinkInfo(a.string, a.get('href')) for a in soup.find('tbody').find_all(BunkrSearcher.__is_album_link)]

    def __get_pages_amount(self, soup: BeautifulSoup) -> int:
        return max([int(div.string.strip()) if div.string.strip().isnumeric() else 0 for div in soup.find('div', class_='mt-4 flex justify-center')])

    def __build_url(self, query: str, page: int = 1) -> str:
        return f'https://www.bunkr-albums.io/?search={query}&page={page}'


def download_results(
        search: BunkrSearch, 
        output_path: Path, content_path: Optional[Path]=None, max_size: Optional[str]=None, max_album_size: Optional[str]=None,
        filter_query: Optional[str]=None, 
        verbose=False):
    
    if not output_path.is_dir():
        raise ValueError(f'Ouptut path {output_path} is not a directory.')
    max_size_int = parse_size_name(max_size) if max_size is not None else None
    max_album_size_int = parse_size_name(max_album_size) if max_album_size is not None else None
    acum_size = 0
    results: List[AlbumInfo] = []
    # TODO: add name mapping (extract with regex) to join results
    for res in search.results:
        if (filter_query is not None) and re.search(filter_query, res.name) is None:
            if verbose:
                print(f"Skipping {res.name} because it didn't match the filter regex")
            continue

        result_size = res.get_size_bytes()
        if max_album_size is not None and result_size > max_album_size_int:
            if verbose:
                print(f'Skipping {res.name} because it exceeded the max size for an album')
            continue
        if max_size is not None and (acum_size + result_size) > max_size_int:
            if verbose:
                print(f'Skipping {res.name} because it will exceed the max download size')
            continue
        
        if verbose:
            print(f'Added {res.name} to downloads')
        acum_size += result_size
        results.append(res)
        res.downloaded = True

    results_len = len(results)
    print(f'Downloading {results_len} album{"s" if results_len > 1 else ""} into {output_path}')
    for res in results:
        safe_name = res.name.replace('/', '|').replace('.', '_')
        prepare_bunkr_scrapper(safe_name, output_path.joinpath(safe_name), content_path).run([res.url])
    

