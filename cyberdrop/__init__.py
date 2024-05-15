import requests
from requests import Response
from typing import Optional, Dict, Any, List, Union, Iterable
import os
from dataclasses import dataclass
from pathlib import Path
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

@dataclass
class CyberDropAlbum:
    id: int
    name: str
    identifier: str
    files: int

    timestamp: int
    editedAt: int
    download: bool
    public: bool
    description: str


@dataclass
class CyberDropUpload:
    id: int
    name: str
    slug: str
    image: str # server for the image -> {image}/{name}
    expirydate: Optional[int]
    albumid: str
    extname: str
    thumb: str

    size: int
    userid: str
    timestamp: int


class Cyberdrop:

    def __init__(self) -> None:
        self.__server_url: str
        self.__albums = None
        self.__albums_updated = False
        self.__albums: List[CyberDropAlbum] = None
        self.__update_server()

    def get_albums(self) -> List[CyberDropAlbum]:
        if self.__albums_updated or self.__albums is None:
            albums = self.__get_request('https://cyberdrop.me/api/albums').json().get('albums')
            self.__albums = [CyberDropAlbum(**a) for a in albums]
            self.__albums_updated = False # Reset flag
        return self.__albums
    
    def get_uploaded_files(self) -> List[CyberDropUpload]:
        page_number = 1
        res = self.__get_request(f'https://cyberdrop.me/api/uploads/{page_number}').json().get('files')
        return [CyberDropUpload(**u) for u in res]

    def download_image(self, file: CyberDropUpload, dest_dir: str, filename: Optional[str]) -> None:
        res = self.__get_request(f'{file.image}/{file.name}')
        image_name = (filename if filename is not None else file.name) + f".{res.headers['content-type'].split('/')[1]}"
        with open(dest_dir + image_name, '+wb') as f:
            f.write(res.content)

    def find_album_by_name(self, name: str) -> Optional[CyberDropAlbum]:
        for album in self.get_albums():
            if album.name == name:
                return album
        return None

    def upload_dir(self, dir: Union[str,Path]):
        dir = dir if isinstance(dir, Path) else Path(dir)
        if not dir.exists():
            raise Exception(f'Could not find dir {dir}')
        if not dir.is_dir():
            raise ValueError(f'{dir} is not a directory')
        
        album = self.find_album_by_name(dir.name)
        if album is None:
            album = self.create_album(dir.name)
        
        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for p in dir.iterdir():
                if p.is_dir() or not p.suffix.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                    continue
                futures[executor.submit(self.upload_file, p, album)] = p.name
            
            for future in concurrent.futures.as_completed(futures):
                file_name = futures[future]
                try:
                    future.result()
                except:
                    print("Failed upload for", file_name)

         
    def create_album(self, name: str, description: Optional[str] = None) -> CyberDropAlbum:
        res = requests.post(
            'https://cyberdrop.me/api/albums',
            json={
                "name": name,
                "description": description if description is not None else ""
            },
            headers=self.__get_headers()
        )
        if not res.ok:
            print("Error", res.content[:100])
            raise Exception(f'Could not create album: {name}')
        self.__albums_updated = True
        new_album = self.find_album_by_name(name)
        if new_album is None:
            print("Create response", res.content)
            raise Exception('Album created but not found')
        return new_album

    def upload_file(self, filepath: Union[str,Path], album: Optional[CyberDropAlbum] = None) -> Optional[str]:
        files = {'files[]': open(filepath,'rb')}
        headers = {**self.__get_headers(), "Albumid": str(album.id)} if album is not None else self.__get_headers()
        res = requests.post(
            self.__get_server_url(),
            files=files,
            headers=headers
            )
        if not res.ok:
            print(f"There was an error uploading image: {res.content}")
        return res.json()['files'][0]['url']
    
    def move_files_to_album(self, files: Iterable[CyberDropUpload], album: CyberDropAlbum):
        res = requests.post(
            'https://cyberdrop.me/api/albums/addfiles',
            json= {
                'ids': map(lambda f: f.id, files),
                'albumid': str(album.id)
            },
            headers=self.__get_headers()
        )
        if not res.ok:
            print("There was an error moving the files")
    
    def bulk_delete(self, files: Iterable[CyberDropUpload]):
        res = requests.post(
            'https://cyberdrop.me/api/upload/bulkdelete',
            json={
                'values': map(lambda f: f.id ,files)
            },
            headers=self.__get_headers()
        )
        if not res.ok:
            raise Exception('Could not delete file')
            
    def __get_server_url(self) -> str:
        if self.__server_url is None:
            self.__update_server()
        return self.__server_url

    def __get_token(self) -> str:
        token = os.environ.get('CYBERDROP_TOKEN')
        if token is None:
            raise Exception('Could not fetch token from environment')
        return token

    def __get_headers(self) -> Dict[str,str]: 
        return {
            'token': self.__get_token() 
        }

    def __get_request(self, url: str) -> Response:
        res = requests.get(url, headers=self.__get_headers())
        content_type = res.headers['content-type']
        if not res.ok:
            error_msg = res.json() if content_type.find('application/json') != -1 else None
            raise Exception(f'Could not update available server{": " + error_msg if error_msg is not None else ""}')
        
        return res

    def __update_server(self) -> None:
        url = self.__get_request('https://cyberdrop.me/api/node').json().get('url')
        if url is None:
            raise Exception(f'Invalid server response from status server')
        self.__server_url = url

if __name__ == '__main__':
    cd = Cyberdrop()
    cd.upload_dir('./Toph')
