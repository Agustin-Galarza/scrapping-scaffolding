from scrapper import Scrapper, FileDownloader, URLScrapper, URLProcessor
from bs4 import BeautifulSoup
from typing import List, Set
from pathlib import Path
import json
import requests
from dataclasses import dataclass
from test import main as download_album


@dataclass
class LinkInfo:
    name: str
    url: str

    def get_album_name(self) -> str:
        return f'{self.name.replace(" Clips/GIFs", "").replace(" Clips", "")}'

    def __hash__(self) -> int:
        return hash(f'{self.name} {self.url}')

    def __str__(self) -> str:
        return f'({self.name}: {self.url})'

@dataclass
class AlbumInfo:
    name: str
    url: str
    files: int
    size: str

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
"""

def save_downloaded(downloaded: List[str], downloaded_path = 'output/downloaded.json') -> None:
    with open(downloaded_path, '+w') as file:
        json.dump(downloaded, file)


def get_downloaded(downloaded_path = 'output/downloaded.json') -> List[str]:
    with open(downloaded_path, '+r') as file:
        downloaded_list = json.load(file)
        return downloaded_list

def cook_soup(url: str) -> BeautifulSoup:
    res = requests.get(url)
    if not res.ok:
        raise Exception(f'Response returned error status {res.status_code}: {res.text}')
    return BeautifulSoup(res.text, 'html.parser')

def get_album_info(url: str) -> AlbumInfo:
    soup = cook_soup(url)
    header_div = soup.find('div', class_='mb-12-xxx')
    if header_div is None:
        raise Exception('Header div not found for album', url)
    
    title = str(header_div.find('h1').string)
    span_items = [i.replace('\n', '').replace('\t','') for i in str(header_div.find('span').string).split(' ', 1)]
    return AlbumInfo(
        name=title,
        url=url,
        files=int(span_items[0].replace('files', '')),
        size=span_items[1].strip('()')
    )

def download_new_albums(downloaded: List[str], downloaded_path: str = 'output/downloaded.json', dry_run = False):
    url = 'https://www.bunkr-albums.io/?search=umeko'
    soup = cook_soup(url)

    list_body = soup.find('tbody')
    if list_body is None:
        raise Exception('No result list found')
    links_info: Set[LinkInfo] = set()
    for a in list_body.find_all('a'):
        if a is None:
            print('Link returned None')
            continue
        content = str(a.string).replace('Umeko J - ', '').replace('UmekoJ - ', '')
        if content == 'Visit' or content in downloaded or content.lower().find('preview') != -1:
            continue
        links_info.add(LinkInfo(content, a.get('href')))
    
    if len(links_info) == 0:
        print("Nothing to download")
        return
    
    for link in links_info:
        album_info = get_album_info(link.url)
        print('------ Preparing download for: ------')
        print(album_info)
        if dry_run:
            continue
        download_album(output_folder='output', output_name=link.get_album_name(), identifier=link.name, url=link.url)
        downloaded.append(link.name)

    if dry_run:
        return
    
    save_downloaded(downloaded, downloaded_path)

def main():
    downloaded_path = 'output/downloaded.json'
    downloaded = get_downloaded(downloaded_path)
    download_new_albums(downloaded, downloaded_path, dry_run=True)

if __name__ == '__main__':
    main()

