"""
Base Detector Class
Defines the contract for all explainable, rule-based AML detectors.
"""

from abc import ABC, abstractmethod
from typing import List
import networkx as nx
from ..schemas import DetectionAlert, CanonicalTransaction


class BaseDetector(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def detect(self, G: nx.MultiDiGraph, transactions: List[CanonicalTransaction]) -> List[DetectionAlert]:
        """
        Executes rule-based pattern detection over the temporal graph.
        Returns a list of DetectionAlert objects strictly adhering to Section 8.2.
        """
        pass
