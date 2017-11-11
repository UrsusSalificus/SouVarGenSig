#!/usr/bin/env python3

""" Masking to only have nucleotides composed of the wanted feature
"""
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
import sys
import os

__author__ = "Titouan Laessle"
__copyright__ = "Copyright 2017 Titouan Laessle"
__license__ = "MIT"

# Wanted factor:
factor = str(sys.argv[1])
# Wanted window size:
window_size = int(sys.argv[2])
# Species genome path:
species_genome = str(sys.argv[3])
# Species feature table path, depends on the type of factor:
if factor in ['LCR', 'TE', 'tandem']:
    species_table = str(sys.argv[4])
    factor_type = 'repeats'
elif factor in ['CDS', 'RNA', 'intron', 'UTR']:
    species_table = str(sys.argv[5])
    factor_type = 'features'
# Output path:
output = str(sys.argv[6])


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
# Fetch a fasta file, and clean it (remove N or n, which stands for "any nucleotides)
# Note that if the fasta file contain multiple sequences, only the first will have its CGR computed !
# Input:
#   - fasta_file : Path to the file containing the sequence one wants the CGR computed on
###
def fetch_fasta(fasta_file):
    # Will only take the first sequence of the fasta file
    try:
        records = list(SeqIO.parse(fasta_file, "fasta"))
    except:
        print("Cannot open %s, check path!" % fasta_file)
        sys.exit()
    return (records)


def reading_line(factor_type, feature_table):
    if factor_type == 'repeats':
        return feature_table.readline().rsplit()
    else:
        return feature_table.readline().split('\t')


def True_if_right_factor_strand(factor_type, actual_line, feature_column, feature_type, strand_column):
    # Watch out for commentaries (thus length 1)
    if len(actual_line) > 1:
        # If bigger than one -> feature line
        if factor_type == 'repeats':
            return actual_line[feature_column].split('/')[0].strip('?') in feature_type
        else:
            return actual_line[feature_column] in feature_type and actual_line[strand_column] == '+'
    else:
        # Else we know it is a commentary = not the right factor...
        return False


def extract_factor(records, factor, factor_type, species_table, output, id_column, feature_column, feature_type,
                   strand_column,
                   start_column, end_column):
    # Checking parent directory of output are present
    checking_parent(output)

    # We will store the records in this list
    factor_records = list()

    with open(species_table, 'r') as feature_table, open(output, 'w') as outfile:
        # Must skip the header (which differs in between feature_table and repeats:
        if factor_type == 'repeats':
            feature_table.readline()
            feature_table.readline()
            feature_table.readline()
            actual_line = reading_line(factor_type, feature_table)
        else:
            line = feature_table.readline()
            # Must skip the headers (varying length)
            while line.startswith('#'):
                line = feature_table.readline()
            actual_line = line.split('\t')

        for each_record in range(len(records)):
            # This string will contain all the nucleotide of the record which are coding
            all_ranges = list()

            # Whenever we are not already at our chromosome part -> skip until at it
            while records[each_record].id != actual_line[id_column]:
                actual_line = reading_line(factor_type, feature_table)

            # We also have to find the first time the wanted feature appears
            while not True_if_right_factor_strand(factor_type, actual_line, feature_column, feature_type,
                                                  strand_column):
                actual_line = reading_line(factor_type, feature_table)

            # This line will be the first result
            all_ranges.append([int(actual_line[start_column]), int(actual_line[end_column])])
            # Always keep track of the last range added to the list
            last_added_range = all_ranges[-1]

            # Continue the search
            actual_line = reading_line(factor_type, feature_table)

            # While from the actual record, continue extracting
            while records[each_record].id == actual_line[id_column]:
                # Only do this for wanted feature
                if True_if_right_factor_strand(factor_type, actual_line, feature_column, feature_type, strand_column):
                    # 1) To detect splicing (which would lead to duplicates):
                    if int(actual_line[start_column]) < last_added_range[0] \
                            and int(actual_line[end_column]) < last_added_range[0]:
                        end_of_splicing = last_added_range[0]
                        while True_if_right_factor_strand(factor_type, actual_line, feature_column, feature_type,
                                                          strand_column) and \
                                        int(actual_line[start_column]) <= end_of_splicing:
                            # We must check each range to see if we do not miss some parts
                            each_previous_range = [0, 0]  # Phony first range end
                            for each_range in all_ranges:
                                # We have to make sure each_previous_range range is not beyond each_range
                                if each_previous_range[1] < each_range[1]:
                                    # 1.1) If spliced bigger than the two neighbour ranges -> go add the middle
                                    # by adding the range from the end of previous to the start of actual
                                    if int(actual_line[start_column]) <= each_previous_range[0] \
                                            and int(actual_line[end_column]) >= each_range[1]:
                                        missing_range = [each_previous_range[1] + 1, each_range[0] - 1]
                                        all_ranges.append(missing_range)
                                        # Whenever we append a missing part, we need to sort all the ranges,
                                        # so that it mainting previous
                                    # 1.2) Else if the start is at least in between start of previous and end of each
                                    elif each_previous_range[0] <= int(actual_line[start_column]) < each_range[1]:
                                        # Check if end of spliced range beyond end of each_range
                                        if int(actual_line[end_column]) > each_range[1]:
                                            # If it is, use end of each_range to calculate intersection
                                            missing_part = ((set(range(int(actual_line[start_column]), each_range[0]))
                                                             - set(range(each_range[0], each_range[1])))
                                                            - set(range(each_previous_range[0],
                                                                        each_previous_range[1])))
                                            # Always check for empty part(may be caused by null intersections)
                                            if bool(missing_part):
                                                missing_range = [min(missing_part), max(missing_part)]
                                                all_ranges.append(missing_range)
                                        # Else, simple case of a range in between 2 other ranges -> intersection
                                        else:
                                            missing_part = ((set(range(int(actual_line[start_column]),
                                                                       int(actual_line[end_column])))
                                                             - set(range(each_range[0], each_range[1])))
                                                            - set(range(each_previous_range[0],
                                                                        each_previous_range[1])))
                                            if bool(missing_part):
                                                missing_range = [min(missing_part) + 1, max(missing_part)]
                                                all_ranges.append(missing_range)
                                    # If none of the case above, the next range may yield something, but always look
                                    # behind Always keep track of the last range for the splicing for
                                    each_previous_range = each_range
                            # Continue searching
                            actual_line = reading_line(factor_type, feature_table)
                            # If we get at the last line, actual_line only have one empty entry
                            if not actual_line[0]:
                                break
                        all_ranges.sort()
                    # 2.1) To detect overlap of this range vs last added one:
                    # If there is one, we must cut the intersection out
                    elif last_added_range[0] >= int(actual_line[start_column]) <= last_added_range[0] \
                            < int(actual_line[end_column]):
                        previous_range = set(range(last_added_range[0], last_added_range[1]))
                        actual_range = set(range(int(actual_line[start_column]), int(actual_line[end_column])))
                        upper_part = actual_range - previous_range
                        all_ranges.append([min(upper_part) + 1, max(upper_part)])
                        # Always keep track of the last range added to the list
                        last_added_range = all_ranges[-1]
                        # Continue searching
                        actual_line = reading_line(factor_type, feature_table)
                    # 3) If no overlap, simply store the factor range
                    elif int(actual_line[start_column]) > last_added_range[1]:
                        all_ranges.append([int(actual_line[start_column]), int(actual_line[end_column])])
                        # Always keep track of the last range added to the list
                        last_added_range = all_ranges[-1]
                        # Continue searching
                        actual_line = reading_line(factor_type, feature_table)
                # If it is not our factor, just continue the search
                else:
                    actual_line = reading_line(factor_type, feature_table)
                # If we get at the last line, actual_line only have one empty entry
                if not actual_line:
                    break

            # We can finally store all the sequences as a single sequence
            factor_only = str()
            for each_range in all_ranges:
                factor_only += records[each_record].seq[each_range[0]:each_range[1]]

            new_record = SeqRecord(seq=factor_only, id='_'.join([factor, records[each_record].id]))
            factor_records.append(new_record)

        # We might end up with records which are too small
        # In this case, we must concatenate them:
        if any([len(each_record) < window_size for each_record in factor_records]):
            concatenated_seq = str()
            for each_record in factor_records:
                concatenated_seq += each_record
            concatenated_records = SeqRecord(seq=concatenated_seq.seq, id=factor)

            # Write the new list of records
            SeqIO.write(concatenated_records, outfile, "fasta")
        else:
            # No need to concatenate -> directly write the new list of records
            SeqIO.write(factor_records, outfile, "fasta")


if factor_type == 'repeats':
    id_column = 4
    feature_column = 10
    # The feature type depends on the wanted feature
    if factor == 'LCR':
        feature_type = 'Low_complexity'
    elif factor == 'TE':
        feature_type = ['DNA', 'LINE', 'LTR', 'SINE', 'Retroposon']
    elif factor == 'tandem':
        feature_type = ['Satellite', 'Simple_repeat']
    strand_column = False  # NOT USED
    start_column = 5
    end_column = 6
else:
    id_column = 0
    feature_column = 2
    # The feature type depends on the wanted feature
    if factor == 'CDS':
        feature_type = 'CDS'
    elif factor == 'RNA':
        feature_type = ['misc_RNA', 'ncRNA', 'rRNA', 'tRNA']
    elif factor == 'intron':
        feature_type = 'intron'
    elif factor == 'UTR':
        feature_type = ['five_prime_UTR', 'three_prime_UTR']
    strand_column = 6
    start_column = 3
    end_column = 4

# Fetch all the records from this species fasta
records = fetch_fasta(species_genome)

extract_factor(records, factor, factor_type, species_table, output, id_column, feature_column, feature_type,
               strand_column,
               start_column, end_column)