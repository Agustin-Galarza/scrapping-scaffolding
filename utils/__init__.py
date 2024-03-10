from tqdm import tqdm
from typing import Optional
from requests import Response
import json


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
        self.pbar = tqdm(total=total, desc=base_description, iterable=True)
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
        # TODO: separate file name from path
        self.stats_filepath: Optional[str] = kwargs.get("stats_filepath", None)
        self.stats = dict(tries=0, fails=0, urls=[])

    def add_stat(self, url: str, success: bool):
        if not self.save_stats:
            return
        self.stats["tries"] += 1
        self.stats["fails"] += 1 if not success else 0
        self.stats["urls"].append(dict(value=url, processed=success))

    def save_stats_in_file(self):
        if not self.save_stats:
            return
        path = (
            self.stats_filepath
            if self.stats_filepath is not None
            else f"./{self.get_name()}-stats.log"
        )
        with open(path, "w+") as file:
            json.dump(self.stats, file)


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
