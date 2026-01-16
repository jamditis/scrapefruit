"""Vision-based extractor using OCR and image analysis."""

import io
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


@dataclass
class VisionExtractionResult:
    """Result from vision-based extraction."""
    success: bool
    text: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    error: Optional[str] = None
    regions: List["TextRegion"] = field(default_factory=list)


@dataclass
class TextRegion:
    """A region of text found in an image."""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    level: int = 5  # 1=page, 2=block, 3=para, 4=line, 5=word
    block_num: int = 0
    line_num: int = 0


class VisionExtractor:
    """
    Extract text and data from screenshots using OCR.

    Uses Tesseract OCR for text extraction with optional
    structure detection for tables, lists, and key-value pairs.
    """

    def __init__(self):
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if required dependencies are available."""
        if not HAS_PIL:
            raise ImportError(
                "Pillow is required for vision extraction. "
                "Install with: pip install Pillow"
            )
        if not HAS_TESSERACT:
            raise ImportError(
                "pytesseract is required for vision extraction. "
                "Install with: pip install pytesseract\n"
                "Also install Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
            )

    @staticmethod
    def is_available() -> bool:
        """Check if vision extraction is available."""
        if not HAS_PIL or not HAS_TESSERACT:
            return False

        # Check if Tesseract binary is accessible
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_text(
        self,
        image_data: bytes,
        lang: str = "eng",
        config: str = "",
    ) -> VisionExtractionResult:
        """
        Extract all text from an image using OCR.

        Args:
            image_data: Raw image bytes (PNG, JPEG, etc.)
            lang: Tesseract language code (eng, fra, deu, etc.)
            config: Additional Tesseract config options

        Returns:
            VisionExtractionResult with extracted text
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (handles PNG with alpha)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Run OCR
            text = pytesseract.image_to_string(image, lang=lang, config=config)

            # Get confidence data
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
            confidences = [c for c in data['conf'] if c != -1]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return VisionExtractionResult(
                success=True,
                text=text.strip(),
                confidence=avg_confidence / 100,  # Normalize to 0-1
            )

        except Exception as e:
            return VisionExtractionResult(
                success=False,
                error=str(e),
            )

    def extract_regions(
        self,
        image_data: bytes,
        lang: str = "eng",
        min_confidence: float = 0.5,
    ) -> VisionExtractionResult:
        """
        Extract text with positional information (bounding boxes).

        Useful for understanding page structure and extracting
        specific regions based on position.

        Args:
            image_data: Raw image bytes
            lang: Tesseract language code
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            VisionExtractionResult with regions list
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Get detailed OCR data
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

            regions: List[TextRegion] = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                conf = data['conf'][i]
                text = data['text'][i].strip()

                # Skip empty or low-confidence results
                if not text or conf == -1 or conf / 100 < min_confidence:
                    continue

                regions.append(TextRegion(
                    text=text,
                    x=data['left'][i],
                    y=data['top'][i],
                    width=data['width'][i],
                    height=data['height'][i],
                    confidence=conf / 100,
                    level=data['level'][i],
                    block_num=data['block_num'][i],
                    line_num=data['line_num'][i],
                ))

            # Combine into full text
            full_text = ' '.join(r.text for r in regions)
            avg_conf = sum(r.confidence for r in regions) / len(regions) if regions else 0

            return VisionExtractionResult(
                success=True,
                text=full_text,
                confidence=avg_conf,
                regions=regions,
            )

        except Exception as e:
            return VisionExtractionResult(
                success=False,
                error=str(e),
            )

    def extract_structured(
        self,
        image_data: bytes,
        lang: str = "eng",
    ) -> VisionExtractionResult:
        """
        Extract text and attempt to identify structure (tables, key-value pairs).

        Uses heuristics to detect:
        - Key: Value patterns
        - Tabular data
        - Lists

        Args:
            image_data: Raw image bytes
            lang: Tesseract language code

        Returns:
            VisionExtractionResult with structured_data dict
        """
        try:
            # First get regions for structure analysis
            regions_result = self.extract_regions(image_data, lang)

            if not regions_result.success:
                return regions_result

            # Also get plain text for pattern matching
            text_result = self.extract_text(image_data, lang)
            full_text = text_result.text

            structured_data = {}

            # Pattern 1: Key-Value pairs (Key: Value, Key = Value, Key - Value)
            kv_patterns = [
                r'^([A-Za-z][A-Za-z0-9\s]{0,30}):\s*(.+)$',
                r'^([A-Za-z][A-Za-z0-9\s]{0,30})=\s*(.+)$',
                r'^([A-Za-z][A-Za-z0-9\s]{0,30})\s+-\s+(.+)$',
            ]

            for line in full_text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                for pattern in kv_patterns:
                    match = re.match(pattern, line)
                    if match:
                        key = match.group(1).strip().lower().replace(' ', '_')
                        value = match.group(2).strip()
                        if key and value:
                            structured_data[key] = value
                        break

            # Pattern 2: Detect potential table structure from regions
            # Group regions by Y coordinate (same row)
            rows: Dict[int, List[TextRegion]] = {}
            for region in regions_result.regions:
                if region.level >= 4:  # Line or word level
                    y_bucket = region.y // 20 * 20  # Group by ~20px rows
                    if y_bucket not in rows:
                        rows[y_bucket] = []
                    rows[y_bucket].append(region)

            # Check if we have consistent column structure
            if len(rows) >= 3:
                # Sort rows by Y, then items by X
                sorted_rows = sorted(rows.items(), key=lambda x: x[0])
                table_data = []

                for y, items in sorted_rows:
                    sorted_items = sorted(items, key=lambda x: x.x)
                    row_text = [item.text for item in sorted_items]
                    if row_text:
                        table_data.append(row_text)

                if table_data:
                    structured_data['_table'] = table_data

            # Pattern 3: Lists (lines starting with bullet, number, dash)
            list_items = []
            list_pattern = r'^[\-\*\•\d+\.]\s*(.+)$'

            for line in full_text.split('\n'):
                line = line.strip()
                match = re.match(list_pattern, line)
                if match:
                    list_items.append(match.group(1).strip())

            if list_items:
                structured_data['_list'] = list_items

            return VisionExtractionResult(
                success=True,
                text=full_text,
                structured_data=structured_data,
                confidence=regions_result.confidence,
                regions=regions_result.regions,
            )

        except Exception as e:
            return VisionExtractionResult(
                success=False,
                error=str(e),
            )

    def extract_by_region(
        self,
        image_data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
        lang: str = "eng",
    ) -> VisionExtractionResult:
        """
        Extract text from a specific region of the image.

        Useful when you know the approximate location of the data
        you want to extract (e.g., "the price is always in the top-right").

        Args:
            image_data: Raw image bytes
            x, y: Top-left corner of region
            width, height: Size of region
            lang: Tesseract language code

        Returns:
            VisionExtractionResult with text from region
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Crop to region
            region = image.crop((x, y, x + width, y + height))

            # Convert cropped region back to bytes
            buffer = io.BytesIO()
            region.save(buffer, format='PNG')
            region_bytes = buffer.getvalue()

            return self.extract_text(region_bytes, lang)

        except Exception as e:
            return VisionExtractionResult(
                success=False,
                error=str(e),
            )

    def extract_with_preprocessing(
        self,
        image_data: bytes,
        lang: str = "eng",
        deskew: bool = True,
        denoise: bool = True,
        threshold: bool = True,
    ) -> VisionExtractionResult:
        """
        Extract text with image preprocessing for better OCR accuracy.

        Preprocessing steps:
        - Deskew: Correct rotation
        - Denoise: Remove noise/artifacts
        - Threshold: Convert to binary (black/white)

        Args:
            image_data: Raw image bytes
            lang: Tesseract language code
            deskew: Apply deskew correction
            denoise: Apply noise reduction
            threshold: Apply binary thresholding

        Returns:
            VisionExtractionResult with extracted text
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Convert to grayscale for preprocessing
            if image.mode != 'L':
                image = image.convert('L')

            # Apply preprocessing
            if threshold:
                # Simple threshold - pixels above 128 become white, below become black
                image = image.point(lambda x: 255 if x > 128 else 0, '1')
                image = image.convert('L')

            if denoise:
                # Basic median filter for noise reduction
                try:
                    from PIL import ImageFilter
                    image = image.filter(ImageFilter.MedianFilter(size=3))
                except Exception:
                    pass  # Skip if filter unavailable

            # Convert back to bytes
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            processed_bytes = buffer.getvalue()

            # Run OCR on preprocessed image
            return self.extract_text(processed_bytes, lang)

        except Exception as e:
            return VisionExtractionResult(
                success=False,
                error=str(e),
            )


# Singleton instance for easy access
_vision_extractor = None


def get_vision_extractor() -> Optional[VisionExtractor]:
    """Get the vision extractor singleton, or None if unavailable."""
    global _vision_extractor

    if not VisionExtractor.is_available():
        return None

    if _vision_extractor is None:
        try:
            _vision_extractor = VisionExtractor()
        except ImportError:
            return None

    return _vision_extractor
