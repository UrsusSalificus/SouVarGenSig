#!/usr/bin/env python3

"""Count different ratios of nucleotides in a sequence
"""
from joblib import Parallel, delayed
import sys
import math
import glob
import numpy
import os

__author__ = "Titouan Laessle"
__copyright__ = "Copyright 2017 Titouan Laessle"
__license__ = "MIT"

# Species abbreviation:
species = str(sys.argv[2])
# Wanted window size:
window_size = int(sys.argv[3])
# Sample size:
sample_size = int(sys.argv[4])
# Wanted number of threads at the same time:
n_threads = int(sys.argv[5])
# Output file:
output = str(sys.argv[6])


###
# Extract all the path of files matching a certain pattern in a directory
###
def extract_path(files_directory, pattern):
    return glob.glob(files_directory + pattern)


###
# Check if parent directory is present, if not create it
###
def checking_parent(file_path):
    # We don't need the file name, so will take everything but the last part
    parent_directories = '/'.join(file_path.split('/')[0:(len(file_path.split('/')) - 1)])
    # As we uses parallel, we ended up we one thread doesn't seeing the directory, attempting
    # creating it, while another just did the same -> error "The file already exist", and stopped everything...
    try:
        if not os.path.exists(parent_directories):
            os.makedirs(parent_directories)
    except:
        pass


###
# Compute the k-mer Frequencies using the Chaos Game Representation (FCGR)
# Inputs:
#   - k_size : k-mer size
#   - CGR :
#       - Either a file (string)
#       - Or a set a of coordinates (list) obtained through CGR_coordinates function
#   - outfile : path to the output file, which will contain the FCGR
#           Note: if empty, will return the FCGR instead of writing a file.
# Output:
#   - Either a file, where each k-mer frequencies are separated by \t
#   - Or the k-mer frequencies stocked ias a list
###
def FCGR_from_CGR(k_size, CGR, outfile):
    #####################
    # 1)  Fetch the coordinates and compute all the boundaries of the grid (for a certain k-mer size)
    #####################

    # If CGR is a string, it must be a path leading to a file containing all the coordinates
    if isinstance(CGR, str):
        x_coord = []
        y_coord = []
        with open(CGR, 'r') as CGR_file:
            for each_coord in CGR_file:
                x_coord.append(float(each_coord.split()[0]))
                y_coord.append(float(each_coord.split()[1]))
        coordinates = [x_coord, y_coord]
    # Else it's a Python list of coordinates
    else:
        coordinates = CGR
    # We take out the k_size-1 first coordinates, are these are the coordinates of words smaller than our
    # wanted k-mer size, and would add small errors later on when counting the frequencies
    for each_xy in [0, 1]:
        coordinates[each_xy] = coordinates[each_xy][k_size - 1::]

    # Now compute the different grid starting boundaries
    # Make sure the decimals are precise enough
    decimals = int(math.pow(10, k_size + 2))
    # Calculate the number of different k-mer we will compute (= number of grid we divide the CGR with)
    grid_size = int(math.pow(4, k_size))
    # Compute all the possible starting coordinates of all these grids
    start_coord_ranges = range(0, int(decimals), int(decimals / math.sqrt(grid_size)))

    #####################
    # 2)  After sorting the x coordinates, go one coordinates at a time, and check if it is a starting boundary
    #####################
    # For x coordinates:
    sort_x = sorted(coordinates[0])
    x_boundaries = []
    which_boundary = 0

    # We can go one sorted x coordinate at a time now:
    for each_coordinates in range(len(sort_x)):
        # If we are a the last coordinate, we must mark any remaining boundaries as empty, and we can stop here (break)
        if each_coordinates == len(sort_x) - 1:
            x_boundaries.append(each_coordinates)
            while len(x_boundaries) != len(start_coord_ranges) + 1:
                x_boundaries.append('empty')
            break
        # First, we see if the i coordinates is a "boundary" of a grid
        # (if bigger/outside of the i grid (represented by 'which_boundary'))
        if sort_x[each_coordinates] >= start_coord_ranges[which_boundary] / decimals:
            # If we are just before the last grid, we cannot have problem of empty grid left (see next if):
            if which_boundary == len(start_coord_ranges) - 1:
                x_boundaries.append(each_coordinates)
                which_boundary += 1
            # In some cases, the i coordinates is not only bigger than the i boundary, but also of i+1
            # (and even the next, so on and so on). In this case, we know that the i boundary
            # does not contain any coordinates ('empty'), and that we can go to the next boundary (which_boundary +1)
            elif sort_x[each_coordinates] >= start_coord_ranges[which_boundary + 1] / decimals:
                while not which_boundary == len(start_coord_ranges) - 1 \
                        and sort_x[each_coordinates] >= start_coord_ranges[which_boundary + 1] / decimals:
                    x_boundaries.append('empty')
                    which_boundary += 1
                x_boundaries.append(each_coordinates)
                which_boundary += 1
            # If not at the before-last grid, or if only bigger to i grid, it is the boundary of the i grid.
            # We then note where we are in the index, and go for the next starting boundary (which_boundary +1)
            else:
                x_boundaries.append(each_coordinates)
                which_boundary += 1
            # If we ended up being at the last grid, the last boundary is simply the last element
            # and we can stop here (break)
            if which_boundary == len(start_coord_ranges):
                x_boundaries.append(len(sort_x))
                break

    #####################
    # 3)  Quite similar step is done for each y coordinates corresponding to each x grids
    #####################
    # We will need the order of indices of x coordinates to do the same operations on y:
    numpy_x = numpy.array(coordinates[0])
    numpy_y = numpy.array(coordinates[1])
    sort_index_x = numpy.argsort(numpy_x)
    y_boundaries = []

    # Can go one starting boundary of grids of x at a time:
    # Note, we don't go for the -1 one, as it is not really a grid, but simply the ultimate grid's ending boundary
    for each_column in range(len(x_boundaries) - 1):
        y_boundaries.append([])

        # We will compute the y boundaries differently depending on whether the x column is empty or not:
        if not x_boundaries[each_column] == 'empty':
            # For each column of grids, we can sort the y of the sorted x, and do the same steps as before
            # First, we must find all the y corresponding to the x in the right grid:

            # In case we are at the last column
            if each_column == len(x_boundaries) - 1:
                corresponding_x_indexes = [x_boundaries[each_column], len(sort_x)]

            # Now in cases next column is an empty column, need the first non-empty one to know the corresponding x
            next_column = each_column + 1
            if x_boundaries[next_column] == 'empty':
                while True:
                    # In cases we have only empty columns left,
                    if next_column == len(x_boundaries) - 1:
                        corresponding_x_indexes = [x_boundaries[each_column], len(sort_x)]
                        break
                    # Else we must find which is the next non-empty
                    if x_boundaries[next_column] == 'empty':
                        next_column += 1
                    else:
                        corresponding_x_indexes = [x_boundaries[each_column], x_boundaries[next_column]]
                        break
            # Otherwise, it's simply the x between the boundaries
            else:
                corresponding_x_indexes = [x_boundaries[each_column], x_boundaries[next_column]]

            # Now that we have the corresponding x indexes, we can find the y of these corresponding x, sort them
            # and do the same operation that was performed on x before
            each_column_y = numpy_y[sort_index_x[corresponding_x_indexes[0]:corresponding_x_indexes[1]]]
            sort_y = numpy.sort(each_column_y)
            which_boundary = 0
            # Now do the same operation (see comments for the x coordinates operation)
            # Note, we do not place the last coordinate break at the beginning here,
            # as it would impede with counting later on.
            for each_coordinates in range(len(sort_y)):
                if sort_y[each_coordinates] >= start_coord_ranges[which_boundary] / decimals:
                    # Penultimate grid
                    if which_boundary == len(start_coord_ranges) - 1:
                        y_boundaries[each_column].append(each_coordinates)
                        which_boundary += 1
                    # Empty grid later on:
                    elif sort_y[each_coordinates] >= start_coord_ranges[which_boundary + 1] / decimals:
                        while not which_boundary == len(start_coord_ranges) - 1 \
                                and sort_y[each_coordinates] >= start_coord_ranges[which_boundary + 1] / decimals:
                            y_boundaries[each_column].append('empty')
                            which_boundary += 1
                        y_boundaries[each_column].append(each_coordinates)
                        which_boundary += 1
                    # Any not special grid
                    else:
                        y_boundaries[each_column].append(each_coordinates)
                        which_boundary += 1
                    # Ultimate grid:
                    if which_boundary == len(start_coord_ranges):
                        y_boundaries[each_column].append(len(sort_y))
                        break
                # If we are at the last coordinate
                if each_coordinates == len(sort_y) - 1:
                    y_boundaries[each_column].append(len(sort_y))
                    while len(y_boundaries[each_column]) != len(start_coord_ranges) + 1:
                        y_boundaries[each_column].append('empty')
                    break

        # Else, the whole column is empty, and must be marked as such:
        else:
            while len(y_boundaries[each_column]) != len(start_coord_ranges) + 1:
                y_boundaries[each_column].append('empty')

    #####################
    # 4)  Using only these y starting boundaries (indexes of y), we can count
    # how many coordinates there is in each boundary
    #####################
    FCGR = []
    # We know use the y boundaries to count the frequencies:
    for each_column in range(len(y_boundaries)):
        for each_kmer in range(len(y_boundaries[each_column]) - 1):
            # next_kmer will help us know which boundary we will use to compare to our actual kmer
            next_kmer = each_kmer + 1
            # If empty, this mean there is no counts for this kmer.
            if y_boundaries[each_column][each_kmer] == 'empty':
                FCGR.append(0)
            # As we subtract, we must have a non-empty index to compare with:
            elif y_boundaries[each_column][each_kmer + 1] == 'empty':
                find_non_empty = True
                while y_boundaries[each_column][next_kmer] == 'empty':
                    # If the ultimate kmer is also empty it simply means that each_kmer was the last boundary
                    if next_kmer == len(start_coord_ranges):
                        FCGR.append(0)
                        find_non_empty = False
                        break
                    # Else, we must keep on searching for the next which is not empty
                    else:
                        next_kmer += 1
                # If we find non-empty boundaries in the next kmers, can use it to count the number of kmer in grid i
                # Note that we add +1 to the index, as we are not as a starting position
                if find_non_empty:
                    # Note: Python start indexing at 0.
                    # To easily count using subtraction we must add +1 to the next index to get the real index.
                    FCGR.append((y_boundaries[each_column][next_kmer]) - y_boundaries[each_column][each_kmer])
            # Else can simply use the next kmer index to count the number of coordinates in the grid
            else:
                FCGR.append((y_boundaries[each_column][next_kmer]) - y_boundaries[each_column][each_kmer])

    # If outfile is non-empty, write the output
    if outfile:
        checking_parent(outfile)
        with open(outfile, 'w') as file:
            for each_count in FCGR:
                file.write(str(each_count) + '\t')
            file.write('\n')
        return FCGR
    # If no 2nd argument was given, outfile is empty (= considered False)
    else:
        return FCGR


###
# Compute various nucleotide ratios using CGRs
# Input:
#   - CGR : Path to the file containing the coordinates of a CGR
#   - window_size
###
def ratios (CGR, window_size):
    FCGR = FCGR_from_CGR(1, CGR, '')

    nA = FCGR[0]
    nC = FCGR[1]
    nT = FCGR[2]
    nG = FCGR[3]

    ratio_A = nA / window_size * 100
    ratio_C = nC / window_size * 100
    ratio_T = nT / window_size * 100
    ratio_G = nG / window_size * 100
    ratio_AG = (nA + nG) / window_size * 100
    ratio_CG = (nC + nG) / window_size * 100
    ratio_TG = (nT + nG) / window_size * 100

    every_ratio = [ratio_A, ratio_C, ratio_T, ratio_G, ratio_AG, ratio_CG, ratio_TG]
    return(every_ratio)


checking_parent(output)
# Opening concatenated file on top level, to avoid rewriting at each record
with open(output, 'w') as outfile:
    # Write column headers
    header = '\t'.join(['record','A','C','T','G','AG','CG', 'TG'])
    outfile.write(header + '\t' + '\n')     # + '\t' to keep same number of column

    # Path to CGR directory
    CGR_directory = '/'.join(['../files/CGRs', '_'.join([str(window_size), str(sample_size)]), species])
    # Get all the different CGRs files path
    all_records = extract_path(CGR_directory + '/', '*')
    # Maintain the initial order of sampling
    all_records.sort(key=lambda r: int(r.split('_')[-1]))

    # Parallel computation for every region:
    every_ratio = Parallel(n_jobs=n_threads)(delayed(ratios)
                                             (all_records[each_region], window_size)
                                             for each_region in range(len(all_records)))

    # Take all the records names from the file paths
    record_names = list()
    for each_record in all_records:
        file_name = os.path.basename(each_record).split('_')
        record_names.append('_'.join([file_name[0], file_name[1], file_name[2]]))

    # Write each region's genomic signature in a single file:
    for each_region in range(len(every_ratio)):
        outfile.write(record_names[each_region] + '\t')
        for each_count in every_ratio[each_region]:
            outfile.write(str(each_count) + '\t')
        outfile.write('\n')





