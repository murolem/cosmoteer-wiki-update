import csv
from typing import Iterable


class LogfileLogger:
    """Disk logger for modification operations."""

    def __init__(self, file_log_paths: list[str]):
        self.file_log_paths = file_log_paths

        # generate log files or clear them out if they exist
        for log_path in file_log_paths:
            open(log_path, "w").close()

        # write initial rows
        self.__write_row(
            ["page title", "param_name", "error status", "old value", "new value", "has value changed?", "notes"]
        )

    def log_value_change(self, page_title: str, param_name: str, value_before: str, value_after: str, note: str | None = None, compare_for_changes: bool = True) -> None:
        """
        Logs a template parameter change.

        :param page_title: Title of the current page.
        :param param_name: Name of the parameter.
        :param value_before: Old value.
        :param value_after: New value.
        :param note: A note.
        :param compare_for_changes: Whether to compare the values.
        Enabled by default. If disabled, nothing will be written in "changed?" column.
        """

        self.__write_row(
            [
                page_title,
                param_name,
                "ok",  # error status
                value_before,
                value_after,
                value_before != value_after if compare_for_changes else None,  # has value changed,
                note
            ]
        )

    def log_param_rename(self, page_title: str, param_old_name: str, param_new_name: str) -> None:
        """
        Logs a template parameter rename.

        :param page_title: Title of the current page.
        :param param_old_name: Name of the parameter.
        :param param_new_name: New name of the parameter.
        """

        self.__write_row(
            [
                page_title,
                param_old_name,
                "ok",  # error status
                "",  # value before
                "",  # value after
                "",  # has value changed
                f"param RENAMED to: {param_new_name}"  # notes
            ]
        )

    def log_param_removal(self, page_title: str, param_name: str, old_value: str | None = None) -> None:
        """
        Logs a template parameter removal.

        :param page_title: Title of the current page.
        :param param_name: Name of the parameter.
        :param old_value: Old value, if you wish to log it.
        """

        self.__write_row(
            [
                page_title,
                param_name,
                "ok",  # error status
                old_value,  # value before
                "",  # value after
                "",  # has value changed
                f"param REMOVED"  # notes
            ]
        )

    def log_error(self, page_title: str, param_name: str, error_text: str, value_before: str = '',
                  value_after: str = '') -> None:
        """
        Logs an error.

        :param page_title: Title of the current page.
        :param param_name: Name of the parameter.
        :param error_text: Text of the error.
        :param value_before: Old value, if relevant.
        :param value_after: New value, if relevant.
        """

        self.__write_row(
            [
                page_title,
                param_name,
                error_text,  # error status
                value_before,
                value_after,
                value_before != value_after  # has value changed
            ]
        )

    def __write_row(self, row: Iterable[str]):
        """Writes given rows to the disk."""

        for filepath in self.file_log_paths:
            with open(filepath, "a", newline="") as f:
                csv_writer = csv.writer(f)
                csv_writer.writerows([row])
