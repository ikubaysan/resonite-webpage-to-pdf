from typing import List, Tuple
import fitz  # PyMuPDF

class Link:
    def __init__(self, uri: str, bounds: Tuple[float, float, float, float]):
        self.uri = uri
        self.bounds = bounds  # (x0, y0, x1, y1)
        self.bounds_width = bounds[2] - bounds[0]
        self.bounds_height = bounds[3] - bounds[1]
        #self.origin = (bounds[0], bounds[1])
        self.origin = (bounds[0], bounds[3])
        #self.origin = (bounds[2], bounds[3])
        #self.origin = (bounds[2], bounds[1])

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

                    if (link['from'].y0 > page.rect.height / 0.75) or (link['from'].y1 > page.rect.height / 0.75):
                        # just a test
                        continue

                    link_obj = Link(link['uri'], (link['from'].x0, link['from'].y0, link['from'].x1, link['from'].y1))
                    page_obj.add_link(link_obj)
            self.pages.append(page_obj)
        doc.close()

    def __repr__(self):
        return f"Document(path={self.local_file_path}, pages={self.pages})"


    def get_resonite_string(self, include_request_data: bool) -> str:
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

        if include_request_data:
            resonite_string = f"{self.url}"
            resonite_string += f"*200*" # Add a dummy HTTP status code
        else:
            resonite_string = ""

        resonite_string += f"{len(self.pages)}"

        for page in self.pages:
            # The first two |-delimited values are the width and height of the page
            resonite_string += f"|{page.size[0]}|{page.size[1]}|"
            resonite_string += f"{len(page.links)}|"
            for link in page.links:
                # Write link's x origin, delimited with a pipe
                resonite_string += f"{link.origin[0]}|"
                # Write link's y origin, delimited with a pipe
                resonite_string += f"{link.origin[1]}|"
                # Write link's width, delimited with a pipe
                resonite_string += f"{link.bounds_width}|"
                # Write link's height, delimited with a pipe
                resonite_string += f"{link.bounds_height}|"
                # Write link's URI
                resonite_string += f"{link.uri}|"

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

def parse_resonite_string(resonite_string: str):
    def get_next_substring(s: str, start_index: int) -> (str, int):
        end_index = s.find('|', start_index)
        if end_index == -1:  # No more delimiters, return the rest of the string
            return s[start_index:], len(s)
        substring_length = end_index - start_index
        return s[start_index:start_index + substring_length], end_index + 1

    index = 0
    page_count_str, index = get_next_substring(resonite_string, index)
    page_count = int(page_count_str)

    for _ in range(page_count):
        page_width, index = get_next_substring(resonite_string, index)
        page_height, index = get_next_substring(resonite_string, index)
        link_count_str, index = get_next_substring(resonite_string, index)
        link_count = int(link_count_str)
        print(f"Page: width={page_width}, height={page_height}, link_count={link_count}")

        for _ in range(link_count):
            link_x_origin, index = get_next_substring(resonite_string, index)
            link_y_origin, index = get_next_substring(resonite_string, index)
            link_width, index = get_next_substring(resonite_string, index)
            link_height, index = get_next_substring(resonite_string, index)
            link_uri, index = get_next_substring(resonite_string, index)
            print(f"Link: x={link_x_origin}, y={link_y_origin}, width={link_width}, height={link_height}, uri={link_uri}")




if __name__ == "__main__":
    pdf_file_path = "./pdf_storage/aHR0cHM6Ly93d3cubmV3Z3JvdW5kcy5jb20=_1709186486.pdf"
    pdf_url = "http://dingo.pinkplayhouse.xyz:2095/pdfs/aHR0cHM6Ly93d3cubmV3Z3JvdW5kcy5jb20=_1709186486.pdf"

    #pdf_path = 'resowiki.pdf'

    document = Document(pdf_file_path, pdf_url)
    print(document)
    print()

    resonite_string = document.get_resonite_string(include_request_data=False)
    print(resonite_string)

    # Removed the URL and status code
    #resonite_string_trimmed = '>612.0|792.0<266.5|289.0|45.0|19.5|https://asdf.com/aboutasdf.html<315.25|321.25|30.0|19.5|https://asdf.com/whatisasdf.html<295.75|353.5|55.5|19.5|https://asdfforums.com/'

    #resonite_string_trimmed = "1|612.0|792.0|3|266.5|289.0|45.0|19.5|https://asdf.com/aboutasdf.html|315.25|321.25|30.0|19.5|https://asdf.com/whatisasdf.html|295.75|353.5|55.5|19.5|https://asdfforums.com/|"
    #print(resonite_string_trimmed)

    #parse_resonite_string(resonite_string_trimmed)

    #rs = "http://dingo.pinkplayhouse.xyz:2095/pdfs/aHR0cDovL2FzZGYuY29t_1709245541.pdf|>612.0|792.0|<266.5|289.0|45.0|19.5|https://asdf.com/aboutasdf.html<315.25|321.25|30.0|19.5|https://asdf.com/whatisasdf.html<295.75|353.5|55.5|19.5|https://asdfforums.com/"
    #Document.parse_resonite_string(rs)
