"""Diff generation module for creating unified diff patches."""

from .generator import DiffGenerator
from .file_reader import FileReader
from .patch_writer import PatchWriter

__all__ = [
    "DiffGenerator",
    "FileReader",
    "PatchWriter",
]
