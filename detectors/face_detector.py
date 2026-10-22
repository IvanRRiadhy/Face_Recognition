from abc import ABC, abstractmethod
from typing import List
import numpy as np
from models.responses import FaceInfo


class BaseFaceDetector(ABC):
    """
    Abstract interface for face detectors.
    Allows replacing YuNet in the future with other models without altering application service logic.
    """

    @abstractmethod
    def detect(self, image: np.ndarray) -> List[FaceInfo]:
        """
        Detect faces in a BGR numpy image.

        Args:
            image: BGR numpy image array (original dimensions).

        Returns:
            List of detected faces with bounding boxes, landmarks, and confidence scores.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the detector model."""
        pass
