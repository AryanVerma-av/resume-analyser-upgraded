import io
from pathlib import Path
from typing import Union, Optional
from pypdf import PdfReader
from docx import Document


def read_pdf(source: Union[str, Path, io.BytesIO, bytes]) -> str:
    """Extract text from PDF file path, BytesIO, or raw bytes."""
    if isinstance(source, bytes):
        stream = io.BytesIO(source)
    else:
        stream = source
    reader = PdfReader(stream)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()


def read_docx(source: Union[str, Path, io.BytesIO, bytes]) -> str:
    """Extract text from DOCX file path, BytesIO, or raw bytes."""
    if isinstance(source, bytes):
        stream = io.BytesIO(source)
    else:
        stream = source
    document = Document(stream)
    text = ""
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text += cell.text + "\n"
    return text.strip()


def extract_text_fallback_strings(data: bytes) -> str:
    """Extract printable strings from raw binary stream as a resilient fallback."""
    import re
    # Extract UTF-16LE strings (common in MS Office binary streams)
    utf16_strings = []
    try:
        raw_utf16 = data.decode("utf-16le", errors="ignore")
        utf16_clean = [line.strip() for line in raw_utf16.splitlines() if len(line.strip()) > 3]
        if utf16_clean:
            utf16_strings = utf16_clean
    except Exception:
        pass

    # Extract printable ASCII/Latin-1 strings
    ascii_strings = []
    try:
        strings = re.findall(rb"[\x20-\x7E\r\n\t]{4,}", data)
        decoded = [s.decode("latin-1", errors="ignore").strip() for s in strings]
        ascii_strings = [s for s in decoded if len(s) > 3]
    except Exception:
        pass

    combined = utf16_strings if len("\n".join(utf16_strings)) > len("\n".join(ascii_strings)) else ascii_strings
    return "\n".join(combined).strip()


def read_legacy_doc(source: Union[str, Path, io.BytesIO, bytes]) -> str:
    """Extract text from legacy Word 97-2003 binary .doc files using olefile Piece Table with string fallback."""
    import struct
    try:
        import olefile
    except ImportError:
        olefile = None

    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            data = f.read()
    elif isinstance(source, io.BytesIO):
        data = source.getvalue()
    else:
        data = source

    if olefile and olefile.isOleFile(io.BytesIO(data)):
        try:
            ole = olefile.OleFileIO(io.BytesIO(data))
            if ole.exists("WordDocument"):
                word_stream = ole.openstream("WordDocument").read()
                if len(word_stream) >= 0x01AA:
                    magic = struct.unpack_from("<H", word_stream, 0)[0]
                    if magic == 0xA5EC:
                        flags = struct.unpack_from("<H", word_stream, 10)[0]
                        use_table_1 = (flags & 0x0200) != 0
                        table_name = "1Table" if use_table_1 else "0Table"

                        if ole.exists(table_name):
                            table_stream = ole.openstream(table_name).read()
                            fcClx = struct.unpack_from("<I", word_stream, 0x01A2)[0]
                            lcbClx = struct.unpack_from("<I", word_stream, 0x01A6)[0]

                            clx = table_stream[fcClx : fcClx + lcbClx]
                            pos = 0
                            while pos < len(clx):
                                type_byte = clx[pos]
                                if type_byte == 0x01:  # ClxPrl
                                    cbPrl = struct.unpack_from("<H", clx, pos + 1)[0]
                                    pos += 3 + cbPrl
                                elif type_byte == 0x02:  # Plcfpcd (Piece Table)
                                    pos += 1
                                    lcbPieceTable = struct.unpack_from("<I", clx, pos)[0]
                                    pos += 4
                                    pcd_data = clx[pos : pos + lcbPieceTable]
                                    n = (lcbPieceTable - 4) // 12
                                    cp_array = [struct.unpack_from("<I", pcd_data, i * 4)[0] for i in range(n + 1)]
                                    pcd_offset = (n + 1) * 4
                                    text_pieces = []
                                    for i in range(n):
                                        pcd = pcd_data[pcd_offset + i * 8 : pcd_offset + (i + 1) * 8]
                                        fc = struct.unpack_from("<I", pcd, 2)[0]
                                        is_ansi = (fc & 0x40000000) != 0
                                        actual_fc = fc & 0x3FFFFFFF
                                        cp_len = cp_array[i + 1] - cp_array[i]
                                        if is_ansi:
                                            offset = actual_fc // 2
                                            raw = word_stream[offset : offset + cp_len]
                                            text_pieces.append(raw.decode("latin-1", errors="replace"))
                                        else:
                                            raw = word_stream[actual_fc : actual_fc + cp_len * 2]
                                            text_pieces.append(raw.decode("utf-16le", errors="replace"))
                                    result_text = "".join(text_pieces)
                                    clean_text = result_text.replace("\r", "\n").replace("\x07", "\t")
                                    parsed = "\n".join(line.strip() for line in clean_text.splitlines() if line.strip())
                                    if len(parsed) > 50:
                                        return parsed
                                    break
                                else:
                                    break
        except Exception:
            pass

    return extract_text_fallback_strings(data)


def read_doc(source: Union[str, Path, io.BytesIO, bytes]) -> str:
    """
    Extract text from a Word .doc file.
    Handles both modern OOXML documents saved with .doc extension and legacy binary Word 97-2003 documents.
    """
    # 1. Try reading as modern DOCX (common when docx is saved/renamed as .doc)
    try:
        docx_text = read_docx(source)
        if docx_text and len(docx_text.strip()) > 30:
            return docx_text
    except Exception:
        pass

    # 2. Try legacy binary .doc parsing
    try:
        doc_text = read_legacy_doc(source)
        if doc_text and len(doc_text.strip()) > 30:
            return doc_text
    except Exception:
        pass

    # 3. Fallback to raw string extraction
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            raw = f.read()
    elif isinstance(source, io.BytesIO):
        raw = source.getvalue()
    else:
        raw = source
    return extract_text_fallback_strings(raw)


def read_resume(source: Union[str, Path, io.BytesIO, bytes], filename: Optional[str] = None) -> Optional[str]:
    """Read resume text from PDF, DOCX, DOC, or TXT source."""
    ext = ""
    if filename:
        ext = Path(filename).suffix.lower()
    elif isinstance(source, (str, Path)):
        ext = Path(source).suffix.lower()

    if ext == ".pdf":
        return read_pdf(source)
    elif ext == ".docx":
        return read_docx(source)
    elif ext == ".doc":
        return read_doc(source)
    elif ext in [".txt", ".text"]:
        if isinstance(source, bytes):
            return source.decode("utf-8", errors="replace").strip()
        elif isinstance(source, io.BytesIO):
            return source.getvalue().decode("utf-8", errors="replace").strip()
        else:
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
    else:
        # Unknown extension: try all formats gracefully
        for reader in [read_pdf, read_docx, read_doc]:
            try:
                res = reader(source)
                if res and len(res.strip()) > 20:
                    return res
            except Exception:
                continue
        # Fallback to UTF-8 / string extraction
        try:
            if isinstance(source, bytes):
                return source.decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
        return None


def extract_quick_name(resume_text: str, fallback_filename: str) -> str:
    """Heuristically extract candidate name from top lines, or fallback to cleaned filename."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    for line in lines[:3]:
        # Typical name line: 2 to 4 words, alphabetic, not an email, phone, or generic header
        words = line.split()
        if 1 <= len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
            if not any(header in line.lower() for header in ["resume", "curriculum", "cv", "profile", "contact", "summary"]):
                return line
    # Fallback to filename without extension
    clean_name = Path(fallback_filename).stem.replace("_", " ").replace("-", " ")
    return clean_name.title()
