import csv
import html
import os
from enum import Enum
from typing import Any, Callable, Dict, Literal, TypeVar, Generic

from utils import EnumDict

# =========================
# = SECTION: TRANSFORMERS =
# =========================

# transformer type for the csv data loader
CsvDataLoaderTransformer = Callable[[list[str]], list[str]]


class BaseTransformer:
    def transform[T](self, data: T) -> T:
        """
        Performs the transform.

        :param data: Data to transform.
        """

        raise NotImplementedError()


class CsvTransformer:
    """Csv transformer."""

    columns: list[int]
    """List of column indices to transform."""

    def __init__(self, columns: list[int] | Literal['all']):
        """
        Setups the transformer.

        :param columns: Either a list of column indices to apply the transform to,
        **or** `all` keyword to apply the transform to all columns.

        :exception Exception: When any index in `columns` is negative.
        """

        # for all columns
        if columns == 'all':
            for i in range(len(columns)):
                self.columns.append(i)

            return

        # for a particular set of columns
        else:
            for i in columns:
                if i >= 0:
                    self.columns.append(i)
                else:
                    raise Exception(f"transformer setup failed: index {i} is out of bounds")

    def transform(self, data: list[str]) -> list[str]:
        """
        Performs the transform.

        :param data: Data to transform.
        """

        raise NotImplementedError()


class CsvTransformerUnescapeHtml(CsvTransformer):
    """Csv transformer for unescaping html."""

    def __init__(self, columns: list[int] | Literal['all']):
        super().__init__(columns)

    def transform(self, data: list[str]) -> list[str]:
        """
        Performs the transform.
        Indices that out of bounds will be ignored.

        :param data: Data to transform.
        """

        data_len = len(data)
        for i in self.columns:
            if i < data_len:
                data[i] = html.unescape(data[i])

        return data


class CsvTransformerStripWhitespace(CsvTransformer):
    """Csv transformer for removing whitespace from both ends of a string (cell)."""

    def __init__(self, columns: list[int] | Literal['all']):
        super().__init__(columns)

    def transform(self, data: list[str]) -> list[str]:
        """
        Performs the transform.
        Indices that out of bounds will be ignored.

        :param data: Data to transform.
        """

        data_len = len(data)
        for i in self.columns:
            if i < data_len:
                data[i] = data[i].strip()

        return data

# =========================
# = SECTION: LOADERS =
# =========================

class BaseInputDataLoader:
    data: Any
    __has_loaded_data: bool

    def __init__(self, input_filepath: str):
        self.input_filepath = input_filepath

    def __assertFileExists(self):
        """Checks whether the input file exists. Throws an error if it doesn't."""

        if not os.path.isfile(self.input_filepath):
            raise Exception("failed to initialize a loader: input path doesn't exist")

    def load(self, transformers: list[BaseTransformer]) -> Any:
        """
        Loads data and returns it.
        Loaded data is stored inside.

        :param transformers: A list of transformer classes that perform various things with data.
        Compatible transformers should inherit from `BaseTransformer`.
        Empty list by default (disabled). Each subsequent transformer receives output of previous transformer.

        :returns Resulting data.
        """

        raise NotImplementedError()

    def extract_page_list(self, extractor_function: Callable[[Any], list[str]]) -> list[str]:
        """
        Extracts page list from the data and returns it.

        :param extractor_function: A function that performs the extraction.
        Takes in the data.
        Must return a list of page titles.
        """

        raise NotImplementedError()


class CsvDataLoader(BaseInputDataLoader):
    data: list[list[str]]
    __has_loaded_data: bool = False

    def __init__(self, input_filepath: str):
        super().__init__(input_filepath)

    def load(self,
             transformers: list[CsvTransformer] = [],
             skip_header_row=False
             ) -> list[list[str]]:
        """
        Loads data and returns it.
        Loaded data is stored inside.

        :param skip_header_row: Whether to skip the first row in case you have a header in your data.
        Disabled by default.
        :param transformers: A list of transformer classes that perform various things with data.
        Compatible transformers can be found under the list of classes that inherit from `CsvTransformer` class.
        Empty list by default (disabled). Each subsequent transformer receives output of previous transformer.

        :exception Exception: When called again.

        :returns A list of rows. Each row is a list of cells (strings).
        """

        if self.__has_loaded_data:
            raise Exception("loading error: already loaded")

        self.__assertFileExists()

        with open(self.input_filename, "r") as f:
            reader = csv.reader(f)
            if skip_header_row:
                next(reader, None)

            self.data = []
            for row in reader:
                for transformer in transformers:
                    row = transformer.transform(row)

                self.data.append(row)

            self.__has_loaded_data = true

        return self.data

    def extract_page_list(self,
                          extractor_function: Callable[[list[str]], str] = lambda row: row[0]) -> list[str]:
        """
        Extracts page list from the data and returns it.

        :param extractor_function: A function that performs the extraction.
        Takes in a row.
        Must return a page title.
        By default, returns the value in the first column.

        :exception Exception: When called before `load()`.
        """

        if self.__has_loaded_data:
            raise Exception("page list extracting error: call load() first")

        page_titles: list[str] = []
        for row in self.data:
            page_titles.append(extractor_function(row))

        return page_titles