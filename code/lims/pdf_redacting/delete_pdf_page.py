import pypdf
import os
import re


def extract_pages_without_patterns(input_pdf, output_pdf, phrase):

    patterns = [
        r"\b\d{4}-\d{4}\b",  # 0000-0000
        r"\bD-\d{5}\b",  # D-00000
        r"\bD[\-\u2010\u2011\u2012\u2013\u2014]\d{5}\b",
        r"\bM-\d{5}\b",  # M-00000
        r"\bX-\d{5}\b",  # X-00000
        r"\bN-\d{4}\b",  # N-0000
        r"\b[A-Z]\d{5}\b",  # A00000
        r"\bP-\d{5}\b",  # P-00000
    ]

    try:
        with open(input_pdf, 'rb') as file:
            reader = pypdf.PdfReader(file)
            writer = pypdf.PdfWriter()

            compiled_patterns = [re.compile(pattern) for pattern in patterns]

            for page_number in range(len(reader.pages)):
                page = reader.pages[page_number]
                text = page.extract_text() or ''  # Ensure it's not None

                contains_phrase = phrase in text
                contains_pattern = any(pattern.search(text) for pattern in compiled_patterns)

                if not contains_pattern or contains_phrase:
                    writer.add_page(page)

            with open(output_pdf, 'wb') as output_file:
                writer.write(output_file)

            print(f"Filtered PDF saved as '{output_pdf}'")
    except FileNotFoundError:
        print(f"Error: The file {input_pdf} does not exist.")
    except PermissionError:
        print(f"Error: Permission denied. Check your file path and permissions.")
    except Exception as e:
        print(f"An error occurred: {e}")


# if __name__ == "__main__":
#     input_pdf = r"C:\Users\ekarwowski\Documents\PDF Case Redaction\M-16759_UnRedacted.pdf"
#     output_pdf = r"C:\Users\ekarwowski\Documents\PDF Case Redaction\pdf-with-deleted-pages.pdf"
#     phrase = input("Enter the phrase to search for: ")
#
#     # Ensure the output path includes a filename
#     if not output_pdf.lower().endswith('.pdf'):
#         print("Error: The output path must include a filename with a .pdf extension.")
#     else:
#         # Ensure the output directory exists
#         output_dir = os.path.dirname(output_pdf)
#         if not os.path.exists(output_dir):
#             os.makedirs(output_dir)
#
#         extract_pages_with_phrase(input_pdf, output_pdf, phrase)
