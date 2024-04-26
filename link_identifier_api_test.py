from LinkIdentification.Document import Document

if __name__ == "__main__":
    pdf_file_path = "./pdf_storage/aHR0cHM6Ly93d3cuZ29vZ2xlLmNvbS8=_1714156482.pdf"
    document = Document(pdf_file_path)

    test_url = document.get_url_at_position(0.83, 0.06, True, 0)

    pass
