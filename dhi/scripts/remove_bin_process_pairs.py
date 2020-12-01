#!/usr/bin/env python
# coding: utf-8

"""
Script to remove one or multiple bin process pairs from a datacard.
Example usage:

# remove a certain bin process pair
> remove_bin_process_pairs.py datacard.txt ch1,ttZ -d output_directory

# remove all processes for a specific bin via wildcards (note the quotes)
> remove_bin_process_pairs.py datacard.txt "ch1,*" -d output_directory

# remove all bins for a specific process via wildcards (note the quotes)
> remove_bin_process_pairs.py datacard.txt "*,ttZ" -d output_directory

# remove bin process pairs listed in a file
> remove_bin_process_pairs.py datacard.txt pairs.txt -d output_directory

Note: The use of an output directory is recommended to keep input files unchanged.
"""

import os
import re

from dhi.datacard_tools import (
    columnar_parameter_directives, ShapeLine, bundle_datacard, manipulate_datacard,
    expand_file_lines,
)
from dhi.util import real_path, multi_match, create_console_logger


logger = create_console_logger(os.path.splitext(os.path.basename(__file__))[0])


def remove_bin_process_pairs(datacard, patterns, directory=None, skip_shapes=False):
    """
    Reads a *datacard* and removes bin process pairs given by a list of *patterns*. A pattern can be
    2-tuple or comma-separated string describing the bin and process patterns, or a file containing
    these patterns.

    When *directory* is *None*, the input *datacard* is updated in-place. Otherwise, both the
    changed datacard and all the shape files it refers to are stored in the specified directory. For
    consistency, this will also update the location of shape files in the datacard. When
    *skip_shapes* is *True*, all shape files remain unchanged (the shape lines in the datacard
    itself are still changed).
    """
    # prepare the datacard path
    datacard = real_path(datacard)

    # expand patterns from files and convert to tuples
    _patterns = []
    for pattern in expand_file_lines(patterns):
        if not isinstance(pattern, (tuple, list)):
            pattern = [p.strip() for p in pattern.split(",")]
        if len(pattern) != 2:
            raise Exception("pattern {} must have length 2".format(pattern))
        _patterns.append(pattern)
    patterns = _patterns

    # when a directory is given, copy the datacard (and all its shape files when not skipping them)
    # into that directory and continue working on copies
    if directory:
        logger.info("bundle datacard files into directory {}".format(directory))
        datacard = bundle_datacard(datacard, directory, skip_shapes=skip_shapes)

    # start removing
    with manipulate_datacard(datacard) as content:
        # keep track of which bins and processes were fully removed
        fully_removed_bin_names = set()
        fully_removed_process_names = set()

        # remove from process rates and remember column indices for removal in parameters
        removed_columns = []
        if content.get("rates"):
            bin_names = content["rates"][0].split()[1:]
            process_names = content["rates"][1].split()[1:]
            process_ids = content["rates"][2].split()[1:]
            rates = content["rates"][3].split()[1:]

            # quick check if all lists have the same lengths
            if not (len(bin_names) == len(process_names) == len(process_ids) == len(rates)):
                raise Exception("the number of bin names ({}), process names ({}), process ids "
                    "({}) and rates ({}) does not match".format(len(bin_names), len(process_names),
                    len(process_ids), len(rates)))

            # go through bin and process names and compare with patterns
            for i, (bin_name, process_name) in enumerate(zip(bin_names, process_names)):
                for b, p in patterns:
                    if multi_match(bin_name, b) and multi_match(process_name, p):
                        logger.info("remove process {} from rates in bin {}".format(
                            process_name, bin_name))
                        removed_columns.append(i)
                        break

            # remove hits
            mask = lambda l: [elem for j, elem in enumerate(l) if j not in removed_columns]
            new_bin_names = mask(bin_names)
            new_process_names = mask(process_names)
            new_process_ids = mask(process_ids)
            new_rates = mask(rates)

            # check if certain bins or processes were removed entirely
            fully_removed_bin_names |= set(bin_names) - set(new_bin_names)
            fully_removed_process_names |= set(process_names) - set(new_process_names)

            # add back reduced lines
            content["rates"][0] = "bin " + " ".join(new_bin_names)
            content["rates"][1] = "process " + " ".join(new_process_names)
            content["rates"][2] = "process " + " ".join(new_process_ids)
            content["rates"][3] = "rate " + " ".join(new_rates)

        # decrease imax in counts
        if content.get("counts") and fully_removed_bin_names:
            # decrement imax when specified
            for i, count_line in enumerate(list(content["counts"])):
                if count_line.startswith("imax"):
                    parts = count_line.split()
                    if len(parts) >= 2 and parts[1] != "*":
                        n_old = int(parts[1])
                        n_new = n_old - len(fully_removed_bin_names)
                        logger.info("decrease imax from {} to {}".format(n_old, n_new))
                        parts[1] = str(n_new)
                        content["counts"][i] = " ".join(parts)
                    break

        # decrease jmax in counts
        if content.get("counts") and fully_removed_process_names:
            # decrement jmax when specified
            for i, count_line in enumerate(list(content["counts"])):
                if count_line.startswith("jmax"):
                    parts = count_line.split()
                    if len(parts) >= 2 and parts[1] != "*":
                        n_old = int(parts[1])
                        n_new = n_old - len(fully_removed_process_names)
                        logger.info("decrease jmax from {} to {}".format(n_old, n_new))
                        parts[1] = str(n_new)
                        content["counts"][i] = " ".join(parts)
                    break

        # remove fully removed bins from observations
        if content.get("observations") and fully_removed_bin_names:
            bin_names = content["observations"][0].split()[1:]
            observations = content["observations"][1].split()[1:]

            removed_obs_columns = []
            for i, bin_name in enumerate(bin_names):
                if bin_name in fully_removed_bin_names:
                    logger.info("remove bin {} from observations".format(bin_name))
                    removed_obs_columns.append(i)

            mask = lambda l: [elem for j, elem in enumerate(l) if j not in removed_obs_columns]
            content["observations"][0] = "bin " + " ".join(mask(bin_names))
            content["observations"][1] = "observation " + " ".join(mask(observations))

        # remove from shape lines
        if content.get("shapes"):
            shape_lines = [ShapeLine(line, j) for j, line in enumerate(content["shapes"])]
            to_remove = []
            for shape_line in shape_lines:
                for b, p in patterns:
                    if multi_match(shape_line.bin, b) and multi_match(shape_line.process, p):
                        logger.info("remove shape line for process {} and bin {}".format(
                            shape_line.process, shape_line.bin))
                        to_remove.append((shape_line.i))
                        break

            # change lines in-place
            lines = [line for j, line in enumerate(content["shapes"]) if j not in to_remove]
            del content["shapes"][:]
            content["shapes"].extend(lines)

        # remove columns from certain parameters
        if content.get("parameters") and removed_columns:
            expr = r"^([^\s]+)\s+({})\s+(.+)$".format("|".join(columnar_parameter_directives))
            for i, param_line in enumerate(list(content["parameters"])):
                m = re.match(expr, param_line.strip())
                if not m:
                    continue

                # split the line
                param_name = m.group(1)
                param_type = m.group(2)
                columns = m.group(3).split()
                if max(removed_columns) >= len(columns):
                    raise Exception("parameter line {} '{} {} ...' has less columns than defined "
                        "in rates".format(i, param_name, param_name))

                # remove columns and update the line
                logger.info("remove {} column(s) from parameter {}".format(
                    len(removed_columns), param_name))
                columns = [c for j, c in enumerate(columns) if j not in removed_columns]
                content["parameters"][i] = " ".join([param_name, param_type] + columns)

        # remove fully removed bins from auto mc stats
        if content.get("auto_mc_stats") and fully_removed_bin_names:
            new_lines = []
            for line in content["auto_mc_stats"]:
                bin_name = line.strip().split()[0]
                if bin_name not in fully_removed_bin_names:
                    new_lines.append(line)
                else:
                    logger.info("remove autoMCStats for bin {}".format(bin_name))

            # change lines in place
            del content["auto_mc_stats"][:]
            content["auto_mc_stats"].extend(new_lines)


if __name__ == "__main__":
    import argparse

    # setup argument parsing
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("input", help="the datacard to read and possibly update (see --directory)")
    parser.add_argument("names", nargs="+", metavar="BIN_NAME,PROCESS_NAME", help="names of bin "
        "process pairs to remove in the format 'bin_name,process_name' or files containing these "
        "pairs line by line; supports patterns")
    parser.add_argument("--directory", "-d", nargs="?", help="directory in which the updated "
        "datacard and shape files are stored; when not set, the input files are changed in-place")
    parser.add_argument("--no-shapes", "-n", action="store_true", help="do not copy shape files to "
        "the output directory when --directory is set")
    parser.add_argument("--log-level", "-l", default="INFO", help="python log level; default: INFO")
    args = parser.parse_args()

    # configure the logger
    logger.setLevel(args.log_level)

    # run the removing
    remove_bin_process_pairs(args.input, args.names, directory=args.directory,
        skip_shapes=args.no_shapes)