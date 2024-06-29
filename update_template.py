import csv
import datetime
import html
import json
import shutil
import string
from time import sleep, strftime
from typing import Any, Callable, Iterable
from datetime import datetime

from mwcleric import AuthCredentials
from mwcleric import TemplateModifierBase
from mwcleric import WikiggClient
from mwparserfromhell.nodes import Template

from LogfileLogger import LogfileLogger
from input_data_loaders import BaseInputDataLoader, CsvDataLoader, CsvTransformerUnescapeHtml, \
    CsvTransformerStripWhitespace
from utils import get_first_list_item_matching_condition

# =====================
# = SETTINGS: GENERAL =
# =====================

credentials = AuthCredentials(user_file="bot")
site = WikiggClient("cosmoteer", credentials=credentials, max_retries_mwc=25)

# TEMPLATE NAME
template_name = "Ship infobox"

# EDIT SUMMARY
summary = "Ship pages data cleanup: ship infobox 'hyperdrive_efficiency' param"

# whether to run the program without doing any changes
dry_run = False

# limit on how many pages to process.
# set to large number to process all the pages.
pages_limit = 11111

# delay for updates in seconds
# note that this is respected even if no updated are actually happen.
updates_delay_seconds = 0

# filename of the output file.
# this file can be used to save any data you need that the logfile can't.
output_filename = "output.csv"

# ========================
# = SETTINGS: INPUT DATA =
# ========================

# [MAIN SWITCH:] whether to use input data
use_input_data = True

# filename of the input file.
# this file is used to load any data you might need.
input_filename = "input.csv"

# input data loader
input_data_loader: CsvDataLoader = CsvDataLoader(input_filename)
if use_input_data:
    input_data_loader.load(
        skip_header_row=True,
        transformers=[
            CsvTransformerUnescapeHtml(columns=[0]),
            CsvTransformerStripWhitespace(columns='all')
        ]
    )

# ===========================
# = SETTINGS: LIST OF PAGES =
# ===========================

# [MAIN SWITCH:] whether to source the page list from input data.
# NOTE: usage of input data (`use_input_data`) must be enabled.
source_pages_from_input_data = True

# a list of page titles to iterate over.
page_titles: list[str] = []

if source_pages_from_input_data:
    if not use_input_data:
        raise Exception("failed to extract page titles from input data: input data is not used")

    page_titles = input_data_loader.extract_page_list()

# =================
# = SCRIPT: SETUP =
# =================

# extensions of the input file
input_ext = input_filename.split(".")[-1]

# this is a timestamp for the current run.
# it is a string compatible with filenames.
# it's used to store logfiles and copies of input data.
file_timestamp_str = strftime("%Y-%m-%d %H-%M-%S", datetime.now().timetuple())

# filepath for a copy of the input file that will be saved for history.
input_copy_rel_filepath = "input copies/" + file_timestamp_str + "." + input_ext

# logger used for logging stuff to a logfile. uses CSV format.
logfile_logger = LogfileLogger([
    "logfile.csv",
    f"logfiles/{file_timestamp_str}.csv"
])

# create a copy of the input file for history, if it's used in the current run
if use_input_data:
    shutil.copyfile(input_filename, input_copy_rel_filepath)

# ================
# = SCRIPT: MAIN =
# ================

# logging things

# indicate dry run
if dry_run:
    print("[[DRY RUN]]")
else:
    print("[[🟠LIVE RUN🟠]]")

# print the summary so have a last chance to see it until it's too late
print("SUMMARY: " + summary)

# print pages count
print(
    "Total pages to process: "
    + str(min(pages_limit, len(page_titles)) if source_pages_from_input_data else "unknown")
)


class TemplateModifier(TemplateModifierBase):
    def update_template(self, template: Template):
        # delay the request so we don't get too many requests error
        sleep(updates_delay_seconds)

        # TemplateModifier is a generic framework for modifying templates
        # It will iterate through all pages containing at least one instance
        # of the specified template in the initialization call below and then
        # update every instance of the template in question with one batched edit per page
        if self.current_page.namespace != 0:
            # don't do anything outside of the main namespace
            # for example, we don't want to modify template documentation or user sandboxes
            return

        # ===========================================

        def get_param_value_from_template(
                param_name: str,
                default_value: str | None = None
        ) -> str:
            """
            Get value of a param from the template.

            :param param_name: Name of the param.

            :param default_value: Default value to return if the param is missing.
            Can only be a string. `None` by default, which is a lack of a default value.
            If the param is missing and no default is not defined, an error will be thrown.
            """

            # check if param is missing
            if not template.has(param_name):
                if default_value is None:
                    # no default
                    raise Exception(
                        f"failed to retrieve param '{param_name}' from the template: param is missing and no default is defined")
                else:
                    # yes default
                    return default_value

            # if param is not missing → get its value
            param_value = template.get(param_name, default=default_value).value

            # convert its value to string and remove whitespace on both sides
            # (which naturally is somehow always there)
            return str(param_value).strip()

        def set_param_value(param_name: str, value: str, *args: object, **kwargs: object) -> None:
            """
            Sets value of a param in the current template.

            `*args` and `**kwargs` are passed through to the underlying `template.add()`.

            :param param_name: Name of the param.
            :param value: Value of the param.
            """

            param_exists = template.has(param_name)
            previous_value = get_param_value_from_template(param_name) if param_exists else None

            if not dry_run:
                template.add(param_name, value, *args, **kwargs)

            logfile_logger.log_value_change(
                self.current_page.page_title,
                param_name,
                previous_value,
                value,  # new value,
                note='param CREATED' if not param_exists else None,  # add a note when param doesn't exist
                compare_for_changes=param_exists
                # if param exists, compare it for changes, otherwise - param is created, so no comparison is needed
            )

        def remove_param(param_name: str, *args: object, **kwargs: object) -> None:
            """
            Removes given param from the template.

            `*args` and `**kwargs` are passed through to the underlying `template.remove()`.

            :param param_name: Name of the param.

            :exception Exception: If param doesn't exist.
            """

            if not template.has(param_name):
                raise Exception(f"failed to remove param '{param_name}': param doesn't exist")

            value = get_param_value_from_template(param_name)

            if not dry_run:
                template.remove(param_name)

            logfile_logger.log_param_removal(
                self.current_page.page_title,
                param_name,
                value
            )

        def rename_param(param_name: str, param_new_name: str) -> None:
            """
            Renames given template parameter.
            This is done by retrieving the param value, adding a new param right before it and deleting the original param.

            :param param_name: Name of the param to rename.
            :param param_new_name: New name for the param.

            :exception Exception: If parameter doesn't exist.
            """

            if not template.has(param_name):
                raise Exception(f"failed to rename param '{param_name}': param doesn't exist")

            # get value
            value = get_param_value_from_template(param_name)

            if not dry_run:
                # add new param
                set_param_value(param_new_name, value, before=param_name)

                # delete old param
                remove_param(param_name)

            logfile_logger.log_param_rename(
                self.current_page.page_title,
                param_name,
                param_new_name
            )

        # ================
        # = SCRIPT: MAIN =
        # ================

        main_param_name = "hyperdrive_efficiency_percentage"

        matching_input_entry = get_first_list_item_matching_condition(input_data_loader.data, lambda entry: entry[0] == self.current_page.page_title)
        if matching_input_entry is None:
            # do nothing...
            logfile_logger.log_error(self.current_page.page_title, main_param_name, 'no matching input entry')
            return

        new_value = "absent"

        set_param_value(main_param_name, new_value)

        # main_param_name = "hyperdrive_efficiency"
        #
        # hyperdrive_efficiency_str = get_param_value_from_template(main_param_name, '')
        # if hyperdrive_efficiency_str == '':
        #     # do nothing...
        #     logfile_logger.log_value_change(self.current_page.page_title, main_param_name, '', '', note="no value")
        #     return
        #
        # hyperdrive_efficiency_int = 0
        # try:
        #     hyperdrive_efficiency_int = int(hyperdrive_efficiency_str.replace('%', ''))
        # except Exception as e:
        #     logfile_logger.log_error(self.current_page.page_title, main_param_name, 'failed to parse param to int',
        #                              hyperdrive_efficiency_str)
        #     return
        #
        # set_param_value("hyperdrive_efficiency_percentage", str(hyperdrive_efficiency_int),
        #                 before="hyperdrive_efficiency")
        # remove_param("hyperdrive_efficiency")

        # any changes made before returning will automatically be saved by the runner
        return


# ======================
# ======================
# ======================

TemplateModifier(
    site,
    template_name,
    summary=summary,
    limit=pages_limit,
    title_list=(page_titles if source_pages_from_input_data else None),
).run()
