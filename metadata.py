from pypdf import PdfReader, PdfWriter

def write_metadata(input_path: str, output_path: str, metadata: dict):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)

    writer.add_metadata(metadata)

    with open(output_path, "wb") as f:
        writer.write(f)


# Misol
write_metadata(
    "101033.pdf",
    "pdftest/101033.pdf",
    {
        "/Title": "Hisobot 123",
        "/Author": "Dilshod",
        "/Custom_Caption": "ID:101033,SHERMAMATOVA MOHLAROYIM G'IYOSIDDIN QIZI",
    }
)