import fitz
import os
from typing import List, Tuple, Union
from LinkIdentification.Link import Link
from LinkIdentification.Page import Page

class Document:
    def __init__(self, local_file_path: str):
        self.local_file_path = local_file_path
        # Get the filename with extension
        self.filename = os.path.basename(self.local_file_path)
        self.pages: List[Page] = []
        self._load_document()

    def _load_document(self):
        doc = fitz.open(self.local_file_path)
        for page in doc:
            page_obj = Page(page.number, (page.rect.width, page.rect.height))
            page_links = page.get_links()
            for link in page_links:
                if link['kind'] == fitz.LINK_URI:
                    # Ignore non-http and non-https links
                    if not link['uri'].startswith('http'):
                        continue
                    link_obj = Link(
                        link['uri'],
                        (link['from'].x0, link['from'].y0, link['from'].x1, link['from'].y1),
                        page.rect.width,
                        page.rect.height
                    )
                    page_obj.add_link(link_obj)
            self.pages.append(page_obj)
        doc.close()

    def get_url_at_position(self, x: float, y: float, normalized_coordinates: bool, page_index: int) -> Union[str, None]:
        if page_index < 0 or page_index >= len(self.pages):
            return None
        page = self.pages[page_index]
        for link in page.links:
            if normalized_coordinates:
                if link.normalized_bounds[0] <= x <= link.normalized_bounds[2] and link.normalized_bounds[1] <= y <= link.normalized_bounds[3]:
                    return link.uri
            else:
                if link.bounds[0] <= x <= link.bounds[2] and link.bounds[1] <= y <= link.bounds[3]:
                    return link.uri
        return None

    def __repr__(self):
        return f"Document(path={self.local_file_path}, pages={self.pages})"