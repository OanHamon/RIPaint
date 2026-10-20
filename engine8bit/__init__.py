"""Moteur 8-bit réutilisable : surface logique basse résolution, palette limitée,
police pixel, sprites ASCII et zones de sécurité pour vidéos verticales."""

from .display import LOGICAL_W, LOGICAL_H, SCALE, FPS, SafeZone
from . import palette, font, sprites

__all__ = ["LOGICAL_W", "LOGICAL_H", "SCALE", "FPS", "SafeZone", "palette", "font", "sprites"]
