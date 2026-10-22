import pytest
from models.responses import ImageDimensions, ValidationReason
from validators.dimension_validator import DimensionValidator


class TestDimensionValidator:
    """
    Tests for DimensionValidator:
    - width <= maxWidth AND height <= maxHeight -> VALID
    - width > maxWidth OR height > maxHeight -> IMAGE_TOO_LARGE
    - smaller images are VALID
    """

    def test_image_smaller_than_maximum_is_valid(self):
        dims = ImageDimensions(width=800, height=600)
        is_valid, reason = DimensionValidator.validate(
            image_dims=dims, max_width=1000, max_height=800
        )
        assert is_valid is True
        assert reason == ValidationReason.VALID

    def test_image_exactly_at_maximum_is_valid(self):
        dims = ImageDimensions(width=1500, height=1500)
        is_valid, reason = DimensionValidator.validate(
            image_dims=dims, max_width=1500, max_height=1500
        )
        assert is_valid is True
        assert reason == ValidationReason.VALID

    def test_width_exceeds_maximum_returns_image_too_large(self):
        dims = ImageDimensions(width=1501, height=1500)
        is_valid, reason = DimensionValidator.validate(
            image_dims=dims, max_width=1500, max_height=1500
        )
        assert is_valid is False
        assert reason == ValidationReason.IMAGE_TOO_LARGE

    def test_height_exceeds_maximum_returns_image_too_large(self):
        dims = ImageDimensions(width=1500, height=1501)
        is_valid, reason = DimensionValidator.validate(
            image_dims=dims, max_width=1500, max_height=1500
        )
        assert is_valid is False
        assert reason == ValidationReason.IMAGE_TOO_LARGE

    def test_both_dimensions_exceed_returns_image_too_large(self):
        dims = ImageDimensions(width=2000, height=1800)
        is_valid, reason = DimensionValidator.validate(
            image_dims=dims, max_width=1500, max_height=1500
        )
        assert is_valid is False
        assert reason == ValidationReason.IMAGE_TOO_LARGE
