import csv
import datetime
import html
import json
import re
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
summary = "Ship pages data cleanup: ship infobox 'crew' param"

# whether to run the program without doing any changes
# NOTE: this functionality is implemented LOCALLY in methods you can see below in `update_template`.
# it WILL NOT WORK anywhere else UNLESS you implement it YOURSELF.
dry_run = False

# limit on how many pages to process.
# set to large number to process all the pages.
pages_limit = 111111111

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
use_input_data = False

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
source_pages_from_input_data = False

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

        def set_param_value(param_name: str, value: str, before: str | None = None, after: str | None = None, *args: object, **kwargs: object) -> None:
            """
            Sets value of a param in the current template.

            `*args` and `**kwargs` are passed through to the underlying `template.add()`.

            :param param_name: Name of the param.
            :param value: Value of the param.
            :param before: Name of a param that our param should go before.
            Specify either this, or `after:`.
            :param after: Name of a param that our param should go after.
            Specify either this, or `before:`.

            :exception Exception: If both `before` and `after` are not specified.
            :exception Exception: If both `before` and `after` are specified.
            :exception Exception: If parameter `before`/`after` is specified and doesn't exist.
            """

            param_exists = template.has(param_name)
            previous_value = get_param_value_from_template(param_name) if param_exists else None

            if after is not None:
                # since template.add doesn't have "after" param, we need to do it ourselves.
                # based on code from local `move_param()`
                if not template.has(after):
                    raise Exception(f"after param '{after}' is missing from the template")

                if param_exists:
                    remove_param(param_name)

                # find the next param after the "after" param, so we can place our param before it
                after_param_index_matches = [i for i in range(len(template.params)) if
                                             template.params[i].name == after]
                # match is guaranteed since we've already checked that template has "after" param
                after_param_index = after_param_index_matches[0]

                if not dry_run:
                    # if "after" param is the last param in the template,
                    # we can simply add our param - it will be appended to the end of param list
                    if after_param_index == len(template.params) - 1:
                        template.add(param_name, value, *args, **kwargs)
                    # otherwise we add our param before the next param after the "after" param
                    else:
                        template.add(param_name, value, before=template.params[after_param_index + 1].name, *args, **kwargs)
            else:
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

        def move_param(param_name: str, before: str | None = None, after: str | None = None) -> None:
            """
            Moves parameter before or after another parameter.
            Specify either `before` or `after`, but not both.
            Will throw an error if any of the parameters do not exist.

            :param param_name: Name of the parameter to move.
            :param before: Name of a param that our param should go before.
            Specify either this, or `after:`.
            :param after: Name of a param that our param should go after.
            Specify either this, or `before:`.

            :exception Exception: If both `before` and `after` are not specified.
            :exception Exception: If both `before` and `after` are specified.
            :exception Exception: If parameter `param_name` doesn't exist.
            :exception Exception: If parameter `before`/`after` doesn't exist.

            :return:
            """

            if before is None and after is None:
                raise Exception("both 'before' and 'after' are 'None'")
            elif (before is not None) and (after is not None):
                raise Exception("both 'before' and 'after' are set")
            elif not template.has(param_name):
                raise Exception(f"param '{param_name}' is missing from the template")

            if before is not None:
                if not template.has(before):
                    raise Exception(f"before param '{before}' is missing from the template")

                param_value = get_param_value_from_template(param_name)
                remove_param(param_name)
                set_param_value(param_name, param_value, before=before)

                logfile_logger.log_param_move(self.current_page.page_title, param_name, before=before)
            else:
                if not template.has(after):
                    raise Exception(f"after param '{after}' is missing from the template")

                param_value = get_param_value_from_template(param_name)
                remove_param(param_name)

                # find the next param after the "after" param, so we can place our param before it
                after_param_index_matches = [i for i in range(len(template.params)) if template.params[i].name == after]
                # match is guaranteed since we've already checked that template has "after" param
                after_param_index = after_param_index_matches[0]

                # if "after" param is the last param in the template,
                # we can simply add our param - it will be appended to the end of param list
                if after_param_index == len(template.params) - 1:
                    set_param_value(param_name, param_value)
                # otherwise we add our param before the next param after the "after" param
                else:
                    set_param_value(param_name, param_value, before=template.params[after_param_index + 1].name)

                set_param_value(param_name, param_value, before=before)

                logfile_logger.log_param_move(self.current_page.page_title, param_name, after=after)

        # ================
        # = SCRIPT: MAIN =
        # ================

        # main_param_name = "hyperdrive_efficiency_percentage"
        #
        # matching_input_entry = get_first_list_item_matching_condition(input_data_loader.data, lambda entry: entry[0] == self.current_page.page_title)
        # if matching_input_entry is None:
        #     # do nothing...
        #     logfile_logger.log_error(self.current_page.page_title, main_param_name, 'no matching input entry')
        #     return
        #
        # new_value = "absent"
        #
        # set_param_value(main_param_name, new_value)

        crew_param_name = "crew"
        suggested_crew_param_name = "suggested_crew"

        # check if param was already added
        if template.has(suggested_crew_param_name):
            # do nothing...
            logfile_logger.log_note(self.current_page.page_title, crew_param_name, "already processed")
            return

        if not template.has(crew_param_name):
            # do nothing...
            logfile_logger.log_error(self.current_page.page_title, crew_param_name, 'param is not present')
            return

        param_value_str = get_param_value_from_template(crew_param_name)
        crew_current = re.search(r"\d+", param_value_str, re.MULTILINE)
        if crew_current is None:
            # do nothing...
            logfile_logger.log_error(self.current_page.page_title, crew_param_name, 'failed to extract the current crew count', param_value_str)
            return

        crew_current = int(crew_current.group(0))

        crew_suggested = re.search(r"Suggested: ([+-]?([0-9]*[.])?[0-9]+)", param_value_str)
        if crew_suggested is None:
            # do nothing...
            logfile_logger.log_error(self.current_page.page_title, crew_param_name, 'failed to extract the suggested crew count', param_value_str)
            return

        crew_suggested = int(crew_suggested.group(1))

        set_param_value(crew_param_name, str(crew_current))
        set_param_value(suggested_crew_param_name, str(crew_suggested), after=crew_param_name)

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
