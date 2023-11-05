from tqdm import tqdm
from typing import Optional


class ShowsProgress:
    def __init__(self) -> None:
        self.pbar: Optional[tqdm] = None
        self.last_fail: int = 1
        self.stats = dict(tries=0, fails=0)
        self.__base_description = ""
        self.__last_progress_update = 0

    def init_progress_bar(self, total: int, base_description) -> None:
        self.pbar = None  # Clear variable
        self.pbar = tqdm(total=total, desc=base_description, iterable=True)
        self.__base_description = base_description

    def update_progress_bar(self):
        if self.pbar is not None:
            update_delta = self.stats["tries"] - self.__last_progress_update
            if self.get_fails() > self.last_fail:
                self.pbar.set_description(
                    f"{self.__base_description} ({self.stats['fails']} fails)"
                )
                self.last_fail = self.get_fails()
            self.pbar.update(n=update_delta)
            self.__last_progress_update = self.stats["tries"]

    def clear_progress_bar(self):
        if self.pbar is not None:
            self.pbar.close()

    def advance_progress(self, update_pbar=True):
        self.stats["tries"] += 1
        if update_pbar:
            self.update_progress_bar()

    def add_fail(self):
        self.stats["fails"] += 1

    def get_fails(self) -> int:
        return self.stats["fails"]

    def get_tries(self) -> int:
        return self.stats["tries"]
