from LinkIdentification.Document import Document
from typing import List, Dict, Union
import os

class DocumentCollection:
    def __init__(self):
        # A dict of filename to Document
        self.documents: Dict[str, Document] = {}

    def add_document(self, local_file_path: str):
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"File not found at path: {local_file_path}")
        document = Document(local_file_path=local_file_path)
        self.documents[document.filename] = document

    def get_document_by_filename(self, filename: str) -> Union[Document, None]:
        return self.documents.get(filename, None)