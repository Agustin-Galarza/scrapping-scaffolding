from tqdm import tqdm
from typing import Optional, List
from requests import Response
import json
from pathlib import Path
import re
import unicodedata

def slugify(value):
    """
    Converts a string to a slug. 
    """
    # Normalize the string to NFKD form
    value = unicodedata.normalize('NFKD', value)
    # Encode to ASCII bytes, ignore non-ascii characters
    value = value.encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    value = value.lower()
    # Replace spaces and special characters with hyphens
    value = re.sub(r'[^a-z0-9]+', '-', value)
    # Strip leading and trailing hyphens
    value = value.strip('-')
    return value

def check_response(response: Response):
    if not response.ok:
        raise Exception(f"Error on request, obtained: {response.status_code}")


class ShowsProgress:
    def __init__(self, *args, **kwargs) -> None:
        try:
            super(ShowsProgress, self).__init__(**kwargs)
        except TypeError:
            super(ShowsProgress, self).__init__()
        self.pbar: Optional[tqdm] = None
        self.last_fail: int = 1
        self.progress = dict(tries=0, fails=0)
        self.__base_description = ""
        self.__last_progress_update = 0

    def init_progress_bar(self, total: int, base_description) -> None:
        self.pbar = None  # Clear variable
        self.pbar = tqdm(total=total, desc=base_description, colour='#a970ff', iterable=True)
        self.__base_description = base_description

    def update_progress_bar(self):
        if self.pbar is not None:
            update_delta = self.progress["tries"] - self.__last_progress_update
            if self.get_fails() > self.last_fail:
                self.pbar.set_description(
                    f"{self.__base_description} ({self.progress['fails']} fails)"
                )
                self.last_fail = self.get_fails()
            self.pbar.update(n=update_delta)
            self.__last_progress_update = self.progress["tries"]

    def clear_progress_bar(self):
        if self.pbar is not None:
            self.pbar.close()

    def advance_progress(self, update_pbar=True):
        self.progress["tries"] += 1
        if update_pbar:
            self.update_progress_bar()

    def add_fail(self):
        self.progress["fails"] += 1

    def get_fails(self) -> int:
        return self.progress["fails"]

    def get_tries(self) -> int:
        return self.progress["tries"]


class HasStats:
    def __init__(self, *args, **kwargs) -> None:
        try:
            super(HasStats, self).__init__(**kwargs)
        except TypeError:
            super(HasStats, self).__init__()
        self.save_stats = kwargs.get("save_stats", False)
        
        self.stats_output_dir: Optional[Path] = Path(kwargs.get("stats_output_dir")) if kwargs.get("stats_output_dir") is not None else None
        self.stats_filename: Optional[Path] = Path(kwargs.get("stats_filename")) if kwargs.get("stats_filename") is not None else None

        # self.stats_filepath: Optional[str] = kwargs.get("stats_filepath", None)

        if self.stats_filename is None:
            try:
                n = self.get_name() if self.get_name() is not None else 'process'
                self.stats_filename = Path(f"{slugify(n)}-stats.json")
            except:
                pass
            try:
                n = kwargs.get('name', None)
                self.stats_filename = Path(f"{slugify(n)}-stats.json")
            except:
                self.stats_filename = Path('stats.json')
        
        if self.stats_output_dir is not None and self.stats_filename is not None and self.stats_output_dir.joinpath(self.get_filename()).exists():
            with self.stats_output_dir.joinpath(self.stats_filename).open("r") as file:
                # print("Loading stats from file", file.name)
                self.stats = json.load(file)
        else:
            # print("Creating new stats")
            self.stats = dict(tries=0, fails=0, urls=[])

    def remove_failed_urls(self) -> None:
        self.stats["urls"] = [url for url in self.stats["urls"] if url["processed"]]
        self.stats['tries'] -= self.stats['fails']
        self.stats['fails'] = 0

    def get_filename(self) -> Path:
        if self.stats_filename is not None:
            return self.stats_filename
        try:
            n = self.get_name() if self.get_name() is not None else 'process'
            self.stats_filename = Path(f"{slugify(n)}-stats.json")
        except Exception as e:
            print("Exception", e)
            self.stats_filename = Path('stats.json')
        finally:
            return self.stats_filename

    def get_stats(self) -> dict:
        return self.stats
    
    def get_all_urls(self) -> List[str]:
        return [url["value"] for url in self.stats["urls"]]

    def get_failed_urls(self) -> List[str]:
        return [url["value"] for url in self.stats["urls"] if not url["processed"]]

    def opt_set_stats_output_dir(self, dir: str) -> None:
        if self.stats_output_dir is None:
            self.stats_output_dir = dir

    def opt_set_stats_filename(self, filename: str) -> None:
        if self.stats_filename is None:
            self.stats_filename = filename

    def get_stats_filepath(self) -> Path:
        self.opt_set_stats_output_dir('./')
        return Path(self.stats_output_dir).joinpath(self.get_filename())
        
    def add_stat(self, url: str, success: bool):
        if not self.save_stats:
            return
        self.stats["tries"] += 1
        self.stats["fails"] += 1 if not success else 0
        self.stats["urls"].append(dict(value=url, processed=success))

    def save_stats_in_file(self):
        if not self.save_stats:
            return
        with self.get_stats_filepath().open("w+") as file:
            json.dump(self.stats, file, indent=4)


class NamedResource:
    @classmethod
    def default_name(cls):
        return cls.__name__

    def __init__(self, *args, **kwargs) -> None:
        try:
            super(NamedResource, self).__init__(**kwargs)
        except TypeError:
            super(NamedResource, self).__init__()
        self.name = kwargs.get("name", self.default_name())

    def get_name(self) -> str:
        return self.name

    def set_name(self, name: str) -> None:
        self.name = name

    def has_default_name(self) -> bool:
        return self.get_name() == self.default_name()
