# -*- coding: utf-8 -*-
"""
Run pahole (https://linux.die.net/man/1/pahole) on a set of specified objects.
"""

import os
import sys
import subprocess

import argparse
import logging
import re
import json
import pathlib

import jsonschema
import coloredlogs


__V_LEVELS__ = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "critical": logging.CRITICAL,
    }

__SCHEMA__ = {
    "type": "object",
    "required": ["paths"],
    "properties": {
        "paths": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source"],
                "properties": {
                    "source": {
                        "type": "array",
                        "items": {"type": "string"}
                        },
                    "blacklist": {
                        "type": "array",
                        "items": {"type": "string"}
                        },
                    },
                },
            },
        "ignore": {
            "type": "array",
            "items": {"type": "string"}
            },
        },
    }

# regex for "pahole -a -A"
__REX_SEARCH__ = re.compile(r'([\w\s_-]+){1}{((\n\s.+){1,}){1}\n}([\w\s_-]+){0,1};\n*')
# regex for "pahole -a -A --packable"
__REX_DETAIL__ = re.compile(r'([\w/._-]+){1}(\(\d+\)+){0,1}\t(\d+){1}\t(\d+){1}\t(\d+){1}\n*')
# regex for bytes packing, deliberatly ignoring bit "packing" since pahole struggles with unnamed members
__REX_TRY_PACK__ = re.compile(r'byte[s]{0,1} hole, try to pack')

__COUNT__ = 0


def _get_counter():
    """
    Helper function to create a global counter for unnamed elements in dwarf files.
    """
    global __COUNT__  # pylint: disable=global-statement
    __COUNT__ = __COUNT__+1
    return __COUNT__


def __as_string__(data):
    """
    Helper function to enforce UTF-8 encoding on bytes and strings.
    """
    if isinstance(data, bytes):
        return data.decode("utf-8")
    if not isinstance(data, str):
        raise ValueError(f"unexpected type {type(data)}, need str")
    return data


def __abort_with_err__(exc):
    """
    Helper function to exit with an error code in case `exc` contains an error message (or exception).
    """
    if exc is None:
        return
    error_str = str(exc).split(":::")
    for lvl, str_ in enumerate(error_str):
        indent = "    " * (lvl+1)
        error_str[lvl] = indent + "|_ " + str_.strip().replace("\n", "\n" + indent + "   ")
    error_str = "\n".join(error_str)
    logging.error("execution failed: \n%s", error_str)
    sys.exit(1)


def _find_paths(pattern):
    """
    Helper function to resolve paths for a given pattern.
    """
    # the following shortcut is used if the given pattern is actually a file. this is required under windows since the pathlib
    # will lower-case the full path if no glob is contained.
    if os.path.isfile(pattern):
        return [pattern]
    path = pathlib.Path(pattern)
    paths = [path.as_posix() for path in pathlib.Path(path.root).glob(str(pathlib.Path("").joinpath(*(path.parts))))]
    paths_ = []
    for path_ in paths:
        add_path = True
        for excl in [".git", ".svn", ".vs"]:
            if excl in path_:
                add_path = False
        if add_path:
            paths_.append(path_)
    return paths_


def _run_pahole(file_, args):
    """
    Executes `pahole` for the givenfile and arguments and provides the output from `stdout` as UTF-8 string.
    This function aborts the execution if any error occurs while executing `pahole`.
    """
    with subprocess.Popen(
            ["pahole", *args, file_], shell=False, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE) as proc:

        stdout_, stderr_ = proc.communicate()
        ret = proc.wait()
        if ret:
            __abort_with_err__(f"Command `pahole` returned with {ret}:::\n{__as_string__(stderr_)}")
    return __as_string__(stdout_)


def _find_elements(file_, ignores, lazy=False):
    """
    Runs `pahole` for the given file, ignores all elements that match the `ignores` list of compiled regular expressions.
    A lazy execution will also execute `pahole` with `--packable` to identify elements whose size can be decreased by
    re-packing. If `lazy` is `False` this function will look for "try to pack" annotations in the execution of `pahole`
    instead, requiring re-ordering of members even if it doesn't lead to smaller object sizes.
    """
    has_packables = False

    if lazy:
        # when using the argument `--packable` pahole will not complain about structures with holes
        # that are not at the end of a structure definition, i.e., where re-sorting does not decrease the size
        # of the element. for such structures, however, adding a new member might trigger a violation in
        # the future, which is why this configuration is considered "lazy"
        matches_detail = __REX_DETAIL__.findall(_run_pahole(file_, ["-a", "-A", "--packable"]))
        matches_detail = {
            match[0]: {
                "element": match[0],
                "size_now": match[2],
                "size_packed": match[3],
                "size_saved": match[4],
                } for match in matches_detail}

    matches_search = __REX_SEARCH__.findall(_run_pahole(file_, ["-a", "-A"]))
    matches_search = matches_search = [
        {
            "pre": match[0],
            "members": match[1],
            "post": match[3],
            } for match in matches_search]

    items = {}
    for item in matches_search:
        item_def = f"{item['pre']}{{ {item['members']}}}{item['post']};"
        last_curly = item_def.rfind("}")
        if last_curly != -1:
            item_def = f"{item_def[:last_curly]}\n{item_def[last_curly:]}"
        item["definition"] = item_def

        name_ = (item["post"] if item["post"] else item["pre"]).strip()
        if not name_:
            name_ = f"unknown_{_get_counter()}"

        item["packable"] = False
        if lazy:
            for name_detail in matches_detail.keys():
                if name_detail in name_:
                    # item is considered packable
                    item.update(matches_detail[name_detail])
                    item["packable"] = True
                    has_packables = True
                    name_ = name_detail

        do_ignore = False
        for ignore in ignores:
            if ignore.match(name_):
                do_ignore = True
                break

        if do_ignore:
            continue  # silently ignore by name

        if not lazy:
            # for non-lazy packing only parse the annotations of the definitions
            # such that all "try to pack" annotations lead to a violation (and requires sorting of members)
            item["packable"] = bool(__REX_TRY_PACK__.findall(item["definition"]))

        has_packables = has_packables or item["packable"]
        items[name_] = item

    return items, has_packables


def _collect_elements(data, err_packable=True, lazy=False):
    """
    Wrapper to collect the `pahole` information on all elements.
    """
    all_elements = {}
    for item in data["paths"]:
        for path_ in item["_paths"]:
            elements, packable = _find_elements(path_, data["_ignore"], lazy=lazy)
            if packable and err_packable:
                logging.error(" # %s", path_)
            else:
                logging.info("   %s", path_)

            if elements:
                for name_, element in elements.items():
                    if name_ in all_elements.keys():  # pylint: disable=consider-iterating-dictionary
                        all_elements[name_]["paths"].append(path_)
                    else:
                        all_elements[name_] = element
                        all_elements[name_]["paths"] = [path_]
    return all_elements


def _dump(items, filename):
    """
    Wrapper to dump the colllected output to files (more readable than plain CLI output).
    """
    block = """
/*
 * {element_name}
 * used in
{file_list}
 */
{definition}
    """.strip()

    elements = []
    for name_, data_ in items.items():
        e_decl = data_["definition"]
        e_list = "\n".join([" * " + item_ for item_ in json.dumps(data_["paths"], indent=2).split("\n")])
        elements.append(block.format(element_name=name_, file_list=e_list, definition=e_decl))

    with open(filename, "w", encoding="utf-8") as file_:
        file_.write("\n\n".join(elements))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def __execute__(args):  # pylint: disable=too-many-locals,too-many-branches
    data = None
    root_rel = os.path.relpath(os.path.dirname(os.path.abspath(args.json)))

    try:
        subprocess.check_call(["pahole", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:  # pylint: disable=bare-except
        __abort_with_err__("Failed to run `pahole --version`::: Please make sure that `pahole` is in your PATH")

    # load configuration and resolve paths

    with open(args.json, "r", encoding="utf-8") as file_:
        data = json.loads(file_.read())
        try:
            jsonschema.validate(data, __SCHEMA__)
        except jsonschema.ValidationError as exc:
            __abort_with_err__(f"JSON validation for '{args.json}' failed: {str(exc)}")

    for idx, item in enumerate(data["paths"]):
        if "blacklist" not in item.keys():
            item["blacklist"] = []

        item["source"] = [os.path.normpath(os.path.join(root_rel, path)).replace("\\", "/") for path in item["source"]]

    data["_ignore"] = []
    if "ignore" in data.keys():
        for ignore in data["ignore"]:
            try:
                pat = re.compile(ignore)
                data["_ignore"].append(pat)
            except Exception as exc:  # pylint: disable=broad-except
                __abort_with_err__(f"Failed to compile '{ignore}' as regular expression:\n{str(exc)}")

    # collect items

    for idx, item in enumerate(data["paths"]):
        logging.debug("")
        logging.info("processing source: %s", json.dumps(item["source"], indent=2))

        paths_ = []
        for path in item["source"]:
            logging.debug("  expanding %s", path)
            paths_.extend(_find_paths(path))

        filter_ = []
        filter_.extend([path for path in paths_ if os.path.basename(path) in item["blacklist"]])
        paths = sorted(list(set(paths_) - set(filter_)))

        if not paths:
            __abort_with_err__(f"Error while processing path {idx}::: No files or folders found for provided configuration")

        logging.debug("the following folders and files will be checked: \n%s", json.dumps(paths, indent=2))
        if filter_:
            logging.debug("skipping paths from blacklist: \n%s", json.dumps(filter_, indent=2))

        item["_paths"] = paths

    # process items and dump output to files

    logging.info("")
    logging.info("checking files")
    packables = {}

    elements = _collect_elements(data, lazy=args.lazy)
    packables = {name_: item for name_, item in elements.items() if item["packable"]}

    file_elements = os.path.splitext(args.json)[0] + "_dump_all.h"
    file_packable = os.path.splitext(args.json)[0] + "_dump_packable.h"

    _dump(elements, file_elements)
    _dump(packables, file_packable)

    # output result on CLI

    if packables:
        __abort_with_err__(
            f"The following elements should be re-packed (check {file_packable})\n{json.dumps(sorted(list(packables.keys())), indent=2)}")

    logging.info("")
    logging.info(":) success")


def __is_json_file__(parser_, arg):
    if not os.path.isfile(arg):
        parser_.error(f"'{arg}' not found / not a file")
        return None
    ext = str.lower(os.path.splitext(arg)[1])
    if ext != ".json":
        parser_.error(f"unsupported file '{arg}': expected '.json' file")
        return None
    return arg


if __name__ == "__main__":
    PARSER_ = argparse.ArgumentParser(
        description="cleanup script")

    PARSER_.add_argument(
        '-v', '--verbosity',
        dest="verbosity",
        default="INFO",
        help="verbosity level, one of %s" % list(__V_LEVELS__.keys()))

    PARSER_.add_argument(
        'json',
        metavar="json-config",
        type=lambda x: __is_json_file__(PARSER_, x),
        help=".json file containing the configuration")

    PARSER_.add_argument(
        '--lazy',
        dest="lazy",
        action='store_true',
        help="if set, stops complaining about holes that could be converted to padding")

    ARGS_ = PARSER_.parse_args()

    if ARGS_.verbosity and not ARGS_.verbosity.lower() in __V_LEVELS__.keys():  # pylint: disable=consider-iterating-dictionary
        PARSER_.error("\nverbosity has to be one of %s" % list(__V_LEVELS__.keys()))

    coloredlogs.install(
        level=__V_LEVELS__[ARGS_.verbosity.lower()],
        fmt='%(asctime)s  %(levelname)-8s  %(message)s',
        datefmt='(%H:%M:%S)')

    logging.info("executing %s ...", os.path.basename(__file__))
    __execute__(ARGS_)
