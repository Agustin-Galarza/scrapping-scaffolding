from bs4 import BeautifulSoup, Tag
from typing import List, Set, Iterable, Optional, Dict, Union, Any, Generic, TypeVar, Type
from pathlib import Path
import json
import requests
from dataclasses import dataclass, asdict
from io_utils.json import JSONable, JSONableDataclass
from typing_extensions import Self
from searcher.download.bunkr import prepare_bunkr_scrapper
import re
from time import time
from .utils import parse_download_name, parse_size_name, parse_size_bytes,Color
from functools import reduce


@dataclass
class Config:
    downloads: Path = Path('./output')
    cache: Path = Path('./cache')

def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        config_path.open('w+').write(json.dumps(asdict(Config()), default=lambda x: str(x)))
    with config_path.open('r') as file:
        c = json.load(file)
        return Config(
            downloads=Path(c['downloads']),
            cache=Path(c['cache'])
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
        return "{: <45} | {: >30} | {: >10} | {}".format(self.name, self.url, self.size, ('Not ' if not self.downloaded else '') + 'Downloaded')


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

@dataclass
class BunkrSearch(JSONable):
    query: str
    results: Dict[int, List[AlbumInfo]]
    results_amount: int
    pages: int
    total_pages: int = None

    def get_albums(self) -> List[AlbumInfo]:
        return list(reduce(lambda x, y: x + y, self.results.values()))
    
    @classmethod
    def from_dict(cls, data: Dict[str,Any]) -> Self:
        results = {int(k): [AlbumInfo(**a) for a in v] for k,v in data['results'].items()}
        return cls(data['query'], results, data['results_amount'], data['pages'])

    def __str__(self) -> str:
        albums = self.get_albums()
        res = "\n".join(["\t\t" + a.short_str() for a in albums])
        return f"""
Search Result for {Color.bold(self.query)}:
\t{Color.underline("Albums found")}: {self.results_amount}
\t{Color.underline("Pages loaded")}: {self.pages}
\t{Color.underline("Total pages")}: {self.total_pages}
\t{Color.underline("Results")}:
{res}

Total Size: {parse_size_bytes(sum([a.get_size_bytes() for a in albums]))}
"""

C=TypeVar('C')

@dataclass
class CacheObject(JSONable, Generic[C]):
    value: C
    expires_at: int
    created_at: int

class CacheManager:
    
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self.cache = self.__load_cache()

    def __load_cache(self) -> Dict[str, CacheObject[Any]]:
        if not self.cache_path.exists():
            return dict()
        with self.cache_path.open('r') as file:
            return json.load(file)

    def save_cache(self) -> None:
        with self.cache_path.open('w+') as file:
            json.dump(self.cache, file,default=lambda x: asdict(x))

    def get(self, key: str, default: Optional[CacheObject[C]]=None, value_cls: Optional[Type[C]]=None) -> Optional[C]:
        data = self.cache.get(key, None)
        if data is None:
            return default
        data = CacheObject(**data)
        if data.expires_at < int(time()):
            self.cache.pop(key)
            return default
        if value_cls is not None:
            try:
                return value_cls.from_dict(data.value)
            except:
                pass
            try:
                return value_cls(**data.value)
            except:
                pass
            try:
                return value_cls(data.value)
            except:
                raise Exception(f'Could not parse value of key {key} to {value_cls}')
        return data.value
    
    def set(self, key: str, value: Any, expires_in: int) -> None:
        self.cache[key] = CacheObject(value, int(time()) + expires_in, int(time()))
        self.save_cache()

    def remove(self, key: str) -> None:
        try:
            self.cache.pop(key)
        except KeyError:
            pass


class BunkrSearcher:

    def __init__(self, config: Config) -> None:
        self.config = config
        self.search_history: List[BunkrSearch] = []
        self.downloads: List[DownloadInfo] = self.__load_downloads()
        self.cache = CacheManager(config.cache.joinpath('searches.json'))

    def search(self, query: str, save: bool = True, max_loaded_pages: int = 1) -> BunkrSearch:
        search_result: BunkrSearch = self.cache.get(query, BunkrSearch(query,{},0,0), BunkrSearch)
        if search_result.total_pages == None:
            soup = cook_soup(self.__build_url(query))
            search_result.total_pages = self.__get_pages_amount(soup)
        for page in range(1, max_loaded_pages+1):
            if page <= search_result.pages and search_result.results[page] != []:
                continue
            l = self.__get_result_links(cook_soup(self.__build_url(query, page)))
            albums = [self.__get_album_info(link.url) for link in l]
            
            search_result.results[page] = albums
            search_result.results_amount += len(albums)
            search_result.pages += 1
       
        if save:
            self.search_history.append(search_result)
        self.cache.set(query, search_result, 3600*24) # Searches last for a day
        return search_result

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
        filter_query: Optional[str]=None, merge_query: Optional[str]=None,
        verbose=False):
    
    if not output_path.is_dir():
        raise ValueError(f'Ouptut path {output_path} is not a directory.')
    max_size_int = parse_size_name(max_size) if max_size is not None else None
    max_album_size_int = parse_size_name(max_album_size) if max_album_size is not None else None
    acum_size = 0
    results: Dict[str, List[AlbumInfo]] = dict()  
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
        m = re.match(merge_query, res.name)
        key = res.name if m is None else res.name[m.start():m.end()]
        results.setdefault(key, []).append(res)
        res.downloaded = True

    results_len = len(results.keys())
    print(f'Downloading {results_len} album{"s" if results_len > 1 else ""} into {output_path}')
    for name, res in results.items():
        safe_name = name.replace('/', '|').replace('.', '_')
        prepare_bunkr_scrapper(safe_name, output_path.joinpath(safe_name), content_path).run([r.url for r in res])
    

