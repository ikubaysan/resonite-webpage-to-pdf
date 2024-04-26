from typing import List, Tuple, Union
from LinkIdentification.Link import Link

class Page:
    def __init__(self, number: int, size: Tuple[float, float]):
        self.number = number
        self.size = size  # (width, height)
        self.links: List[Link] = []

    def add_link(self, link: Link):
        self.links.append(link)

    def __repr__(self):
        return f"Page(number={self.number}, size={self.size}, links={self.links})"
