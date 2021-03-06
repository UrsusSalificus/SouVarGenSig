#!/usr/bin/env python3

"""This script compute k-mer frequencies using CGR of all windows of a certain size
"""
import sys
import subprocess

__author__ = "Titouan Laessle"
__copyright__ = "Copyright 2017 Titouan Laessle"
__license__ = "MIT"

# Path to the FCGRs of the species' whole genome:
FCGRs = str(sys.argv[1])
# Path to the distance matrix of FCGRs of the species' whole genome:
dist = str(sys.argv[2])
# Output file:
output = str(sys.argv[3])

center_indexes = subprocess.getoutput('Rscript scripts/get_center.R ' + dist)
# Note, we remove 1 to stick to python calculating range (starting at 0)
center_indexes = [int(each_window) - 1 for each_window in center_indexes.split()]
center_indexes.sort()

with open(FCGRs, 'r') as infile, open(output, 'w') as outfile:
    line = infile.readline()
    # Start the countdown at one -> already red one line
    i = 0
    for each_index in range(len(center_indexes)):
        # Keep going til we are at the right index/line on the FCGR file
        while i < center_indexes[each_index]:
            line = infile.readline()
            i += 1
        # Prepare the line to have the id of "center" instead of the record's id
        good_line = line.split()
        good_line[0] = 'center'
        for each_count in good_line:
            outfile.write(each_count + '\t')
        outfile.write('\n')
