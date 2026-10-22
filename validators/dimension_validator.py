from typing import Tuple
from models.responses import ImageDimensions, ValidationReason


class DimensionValidator:
    """
    Validates that the decoded image dimensions do not exceed the requested maximums.
    width <= maxWidth AND height <= maxHeight -> passes.
    width > maxWidth OR height > maxHeight -> rejects with IMAGE_TOO_LARGE.
    """

    @staticmethod
    def validate(
        image_dims: ImageDimensions,
        max_width: int,
        max_height: int,
    ) -> Tuple[bool, ValidationReason]:
        if image_dims.width > max_width or image_dims.height > max_height:
            return False, ValidationReason.IMAGE_TOO_LARGE

        return True, ValidationReason.VALID
