from typing import List, Tuple
import fitz  # PyMuPDF

class Link:
    def __init__(self, uri: str, bounds: Tuple[float, float, float, float]):
        self.uri = uri
        self.bounds = bounds  # (x0, y0, x1, y1)
        self.bounds_width = bounds[2] - bounds[0]
        self.bounds_height = bounds[3] - bounds[1]
        self.origin = (bounds[0], bounds[1])

    def __repr__(self):
        return f"Link(uri={self.uri}, bounds={self.bounds}) bounds_width={self.bounds_width}, bounds_height={self.bounds_height}, origin={self.origin}"

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
    def __init__(self, local_file_path: str, url: str):
        self.local_file_path = local_file_path
        self.url = url
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
                    link_obj = Link(link['uri'], (link['from'].x0, link['from'].y0, link['from'].x1, link['from'].y1))
                    page_obj.add_link(link_obj)
            self.pages.append(page_obj)
        doc.close()

    def __repr__(self):
        return f"Document(path={self.local_file_path}, pages={self.pages})"


    def get_resonite_string(self) -> str:
        """
        :return:
        A string of this structure, without the line breaks.
        This is for a document with 2 pages, each containing 2 links:

        URL|

        >PAGE0_WIDTH|PAGE0_HEIGHT|<LINK0_X_ORIGIN|LINK0_Y_ORIGIN|LINK0_WIDTH|LINK0_HEIGHT|
        LINK0_URI<LINK1_X_ORIGIN|LINK1_Y_ORIGIN|LINK1_WIDTH|LINK1_HEIGHT|LINK1_URI

        >PAGE1_WIDTH|PAGE1_HEIGHT|<LINK0_X_ORIGIN|LINK0_Y_ORIGIN|LINK0_WIDTH|LINK0_HEIGHT|
        LINK0_URI<LINK1_X_ORIGIN|LINK1_Y_ORIGIN|LINK1_WIDTH|LINK1_HEIGHT|LINK1_URI
        """

        resonite_string = f"{self.url}|"

        for page in self.pages:
            resonite_string += ">" # Indicate start of a new page

            # The first two |-delimited values are the width and height of the page
            resonite_string += f"{page.size[0]}|{page.size[1]}|"

            for link in page.links:
                resonite_string += "<" # Indicate start of a link object
                # Write link's x origin, delimited with a pipe
                resonite_string += f"{link.origin[0]}|"
                # Write link's y origin, delimited with a pipe
                resonite_string += f"{link.origin[1]}|"
                # Write link's width, delimited with a pipe
                resonite_string += f"{link.bounds_width}|"
                # Write link's height, delimited with a pipe
                resonite_string += f"{link.bounds_height}|"
                # Write link's URI
                resonite_string += f"{link.uri}"

        return resonite_string

    @staticmethod
    def parse_resonite_string(resonite_string: str):
        char_index = 0

        # Get the URL
        # Find the index of the first "|" character
        url_end_index = resonite_string.find("|", char_index)
        url = resonite_string[char_index:url_end_index]
        char_index += url_end_index + 1

        # While we can find a ">" character...
        while char_index < len(resonite_string):
            # Get the page width and height
            page_width_end_index = resonite_string.find("|", char_index)
            page_width = float(resonite_string[char_index:page_width_end_index])
            char_index = page_width_end_index + 1

            page_height_end_index = resonite_string.find("|", char_index)
            page_height = float(resonite_string[char_index:page_height_end_index])
            char_index = page_height_end_index + 1

            # While we can find a "<" character...
            while resonite_string[char_index] == "<":
                # Get the link's x origin
                link_x_origin_end_index = resonite_string.find("|", char_index)
                link_x_origin = float(resonite_string[char_index:link_x_origin_end_index])
                char_index = link_x_origin_end_index + 1

                # Get the link's y origin
                link_y_origin_end_index = resonite_string.find("|", char_index)
                link_y_origin = float(resonite_string[char_index:link_y_origin_end_index])
                char_index = link_y_origin_end_index + 1

                # Get the link's width
                link_width_end_index = resonite_string.find("|", char_index)
                link_width = float(resonite_string[char_index:link_width_end_index])
                char_index = link_width_end_index + 1

                # Get the link's height
                link_height_end_index = resonite_string.find("|", char_index)
                link_height = float(resonite_string[char_index:link_height_end_index])
                char_index = link_height_end_index + 1

                # Get the link's URI
                link_uri_end_index = resonite_string.find("|", char_index)
                link_uri = resonite_string[char_index:link_uri_end_index]
                char_index = link_uri_end_index + 1

                print(f"Link: x={link_x_origin}, y={link_y_origin}, width={link_width}, height={link_height}, uri={link_uri}")

            # Move to the next page
            char_index += 1

        return




if __name__ == "__main__":
    pdf_file_path = 'asdf.pdf'
    pdf_url = "http://dingo.pinkplayhouse.xyz:2095/pdfs/aHR0cDovL2FzZGYuY29t_1709245541.pdf"
    #pdf_path = 'resowiki.pdf'

    # document = Document(pdf_file_path, pdf_url)
    # print(document)
    # print()
    # print(document.get_resonite_string())

    rs = "http://dingo.pinkplayhouse.xyz:2095/pdfs/aHR0cDovL2FzZGYuY29t_1709245541.pdf|>612.0|792.0|<266.5|289.0|45.0|19.5|https://asdf.com/aboutasdf.html<315.25|321.25|30.0|19.5|https://asdf.com/whatisasdf.html<295.75|353.5|55.5|19.5|https://asdfforums.com/"
    Document.parse_resonite_string(rs)
