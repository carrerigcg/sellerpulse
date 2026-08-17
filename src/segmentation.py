"""Camada de segmentação — funções puras.

Cada função recebe conexão SQLite + janela temporal e devolve DataFrame.
Sem side effects: leitura pura, sem prints, sem HTTP, sem escrita.
"""

from __future__ import annotations

import sqlite3

import pandas as pd
