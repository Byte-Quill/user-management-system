"""Content-sniffing upload validators (magic-byte checks)."""
import os

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

def validate_file_content(file_obj: UploadedFile):
    """Validate the file's content matches its extension (magic-byte sniff).

    Extension checks alone are bypassed by renaming an executable to .pdf, so
    we inspect actual bytes: start-of-file signatures plus, where cheap,
    end-of-file markers (JPEG EOI, PDF %%EOF) to catch truncated/polyglot files.
    """
    ext = os.path.splitext(file_obj.name)[1].lower()
    head = file_obj.read(16)
    file_obj.seek(0)

    if ext in (".jpg", ".jpeg"):
        # SOI marker at start; EOI marker must appear within the last 4 KB.
        if not head.startswith(b"\xff\xd8\xff"):
            raise ValidationError("File content does not match the '.jpg/.jpeg' extension.")
        file_obj.seek(max(0, file_obj.size - 4096))
        tail = file_obj.read()
        file_obj.seek(0)
        if b"\xff\xd9" not in tail:
            raise ValidationError("Image file appears truncated (missing end marker).")

    elif ext == ".png":
        if not head.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError("File content does not match the '.png' extension.")

    elif ext == ".pdf":
        # %PDF- at the start and %%EOF within the last 1 KB are required by the
        # spec. A real PDF always ends with %%EOF; executables do not.
        if not head.startswith(b"%PDF-"):
            raise ValidationError("File content does not match the '.pdf' extension.")
        file_obj.seek(max(0, file_obj.size - 1024))
        tail = file_obj.read()
        file_obj.seek(0)
        if b"%%EOF" not in tail:
            raise ValidationError("PDF file appears truncated or malformed.")

