from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str]) -> None:
        super().__init__()
        self._headers = tuple(headers)
        self._rows: list[tuple[str, ...]] = []
        self._search_texts: list[str] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        return self.value_at(index.row(), index.column())

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]

        return section + 1 if orientation == Qt.Vertical else None

    def replace_rows(self, rows: list[tuple[str, ...]]) -> None:
        self.beginResetModel()
        self._rows = [self._fit_row(row) for row in rows]
        self._search_texts = [" ".join(row).casefold() for row in self._rows]
        self.endResetModel()

    def clear(self) -> None:
        self.replace_rows([])

    def set_cell(self, row: int, column: int, value: str) -> None:
        if not (0 <= row < len(self._rows) and 0 <= column < len(self._headers)):
            return

        current = list(self._rows[row])
        current[column] = value
        self._rows[row] = tuple(current)
        self._search_texts[row] = " ".join(self._rows[row]).casefold()
        index = self.index(row, column)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

    def headers(self) -> tuple[str, ...]:
        return self._headers

    def row_values(self, row: int) -> tuple[str, ...]:
        return self._rows[row]

    def value_at(self, row: int, column: int) -> str:
        if not (0 <= row < len(self._rows) and 0 <= column < len(self._headers)):
            return ""
        return self._rows[row][column]

    def search_text(self, row: int) -> str:
        if not 0 <= row < len(self._search_texts):
            return ""
        return self._search_texts[row]

    def _fit_row(self, row: tuple[str, ...]) -> tuple[str, ...]:
        values = tuple(str(value) for value in row)
        if len(values) == len(self._headers):
            return values
        if len(values) > len(self._headers):
            return values[: len(self._headers)]
        return values + ("",) * (len(self._headers) - len(values))


class ResultsFilterProxyModel(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self._query = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_query(self, query: str) -> None:
        self._query = query.strip().casefold()
        self.invalidateFilter()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        if not self._query:
            return True

        model = self.sourceModel()
        if not isinstance(model, ResultsTableModel):
            return True

        return self._query in model.search_text(source_row)
