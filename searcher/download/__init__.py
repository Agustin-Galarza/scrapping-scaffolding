from typing import List, Set, Iterable, Optional, Dict, Union
from pathlib import Path
from searcher.download.bunkr import prepare_bunkr_scrapper
import re

from .. import BunkrSearch, AlbumInfo
from ..utils import parse_size_name, parse_download_name

class BunkrDownloader:

    def __init__(self) -> None:
        pass

    def download(
            self,
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
            safe_name = parse_download_name(res.name)
            prepare_bunkr_scrapper(safe_name, output_path.joinpath(safe_name), content_path).run([res.url])