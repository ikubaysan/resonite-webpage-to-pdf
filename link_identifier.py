from typing import List, Tuple
import fitz  # PyMuPDF

class Link:
    def __init__(self, uri: str, bounds: Tuple[float, float, float, float]):
        self.uri = uri
        self.bounds = bounds  # (x0, y0, x1, y1)

    def __repr__(self):
        return f"Link(uri={self.uri}, bounds={self.bounds})"

class Page:
    def __init__(self, number: int, size: Tuple[float, float]):
        self.number = number
        self.size = size  # (width, height)
        self.links: List[Link] = []

    def add_link(self, link: Link):
        self.links.append(link)

    def __repr__(self):
        return f"Page(number={self.number}, size={self.size}, links={self.links})"

class Document:
    def __init__(self, path: str):
        self.path = path
        self.pages: List[Page] = []
        self._load_document()

    def _load_document(self):
        doc = fitz.open(self.path)
        for page in doc:
            page_obj = Page(page.number, (page.rect.width, page.rect.height))
            page_links = page.get_links()
            for link in page_links:
                if link['kind'] == fitz.LINK_URI:
                    link_obj = Link(link['uri'], (link['from'].x0, link['from'].y0, link['from'].x1, link['from'].y1))
                    page_obj.add_link(link_obj)
            self.pages.append(page_obj)
        doc.close()

    def __repr__(self):
        return f"Document(path={self.path}, pages={self.pages})"

# Example usage
pdf_path = 'asdf.pdf'
document = Document(pdf_path)
print(document)
