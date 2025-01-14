"""Adapted from https://github.com/snufoodbiochem/Alphafold3_tools"""

import json
import sys
import os
import re

from itertools import product
from string import ascii_uppercase


def generate_ids(start_index, count):
    sequence = []
    length = 1
    while len(sequence) < count:
        for item in product(ascii_uppercase, repeat=length):
            if len(sequence) == count:
                break
            if start_index > 0:
                start_index -= 1
                continue
            sequence.append("".join(item[::-1]))
        length += 1
    return sequence


def parse_modifications(id_line, sequence_type):
    """
    Parse modifications from the ID line.

    :param id_line: The ID line from the FASTA file.
    :param sequence_type: The type of the sequence (protein, dna, rna, or ligand).
    :return: A list of modifications as dictionaries.
    """
    modifications = []
    matches = re.findall(r"&(\d+)_([A-Za-z]{3})", id_line)
    for match in matches:
        position = int(match[0])  # Extract the numeric position
        mod_type = match[1]  # Extract the 3-letter modification type

        if sequence_type == "protein":
            modifications.append({"ptmType": mod_type, "ptmPosition": position})
        elif sequence_type in {"dna", "rna"}:
            modifications.append(
                {"modificationType": mod_type, "basePosition": position}
            )
        elif sequence_type == "ligand":
            modifications.append({"modificationType": mod_type, "position": position})
    return modifications


def parse_bonded_atom_pairs(id_line, id_list):
    """
    Parse bonded atom pairs from the ID line.

    :param id_line: The ID line containing bonded atom information.
    :param id_list: A list of IDs corresponding to the sequence.
    :return: A list of bonded atom pairs in JSON-compatible format.
    """
    bonded_atom_pairs = []
    matches = re.findall(r"&(\d+)_([A-Za-z0-9]+)_(\d+)_([A-Za-z0-9]+)", id_line)

    for match in matches:
        atom1_position = int(match[0])
        atom1_type = match[1]
        atom2_position = int(match[2])
        atom2_type = match[3]

        for id_prefix in id_list:  # Add bonded atom pairs for each ID
            bonded_atom_pairs.append(
                [
                    [id_prefix, atom1_position, atom1_type],
                    [id_prefix, atom2_position, atom2_type],
                ]
            )

    return bonded_atom_pairs


def fasta_to_json(fasta_file):
    # Generate the output JSON file name
    json_file = os.path.splitext(fasta_file)[0] + ".json"

    # Extract the base name for "name" field
    json_name = os.path.splitext(os.path.basename(fasta_file))[0]

    with open(fasta_file, "r", encoding="utf-8") as file:
        lines = file.readlines()

    sequences = []
    current_name = None
    current_sequence = []
    last_id_end = 0  # Track the last used letter index for IDs (0 = 'A')
    bonded_atom_pairs = []

    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            # Save the previous sequence if it exists
            if current_name is not None:
                # Parse ID from current_name
                name_parts = current_name.split("#")

                count = int(name_parts[1]) if len(name_parts) > 1 else 1
                id_list = generate_ids(last_id_end, count)
                last_id_end += count  # Update the last used index

                sequence_type = "protein"
                if "dna" in current_name:
                    sequence_type = "dna"
                elif "rna" in current_name:
                    sequence_type = "rna"
                elif "ligand" in current_name:
                    sequence_type = "ligand"
                elif "smile" in current_name:
                    sequence_type = "smile"

                modifications = parse_modifications(current_name, sequence_type)

                if sequence_type in {"protein", "dna", "rna"}:
                    sequences.append(
                        {
                            sequence_type: {
                                "id": id_list,
                                "sequence": "".join(current_sequence)
                                .replace(" ", "")
                                .upper(),
                                "modifications": modifications,
                            }
                        }
                    )
                elif sequence_type == "ligand":
                    ligand_sequence = "".join(current_sequence).replace(" ", "").upper()
                    if "," in ligand_sequence:
                        ccdCodes = ligand_sequence.split(",")
                    else:
                        ccdCodes = [ligand_sequence]
                    bonded_atom_pairs.extend(
                        parse_bonded_atom_pairs(current_name, id_list)
                    )
                    sequences.append({"ligand": {"id": id_list, "ccdCodes": ccdCodes}})
                elif sequence_type == "smile":
                    sequences.append(
                        {
                            "ligand": {
                                "id": id_list,
                                "smiles": "".join(current_sequence).replace(" ", ""),
                            }
                        }
                    )

            # Start a new sequence
            current_name = line[1:]
            current_sequence = []
        else:
            current_sequence.append(line)

    # Add the last sequence
    if current_name is not None:
        name_parts = current_name.split("#")
        # name = name_parts[0]
        count = int(name_parts[1]) if len(name_parts) > 1 else 1
        id_list = generate_ids(last_id_end, count)
        last_id_end += count  # Update the last used index

        sequence_type = "protein"
        if "dna" in current_name:
            sequence_type = "dna"
        elif "rna" in current_name:
            sequence_type = "rna"
        elif "ligand" in current_name:
            sequence_type = "ligand"
        elif "smile" in current_name:
            sequence_type = "smile"

        modifications = parse_modifications(current_name, sequence_type)

        if sequence_type in {"protein", "dna", "rna"}:
            sequences.append(
                {
                    sequence_type: {
                        "id": id_list,
                        "sequence": "".join(current_sequence).replace(" ", "").upper(),
                        "modifications": modifications,
                    }
                }
            )
        elif sequence_type == "ligand":
            ligand_sequence = "".join(current_sequence).replace(" ", "").upper()
            if "," in ligand_sequence:
                ccdCodes = ligand_sequence.split(",")
            else:
                ccdCodes = [ligand_sequence]
            bonded_atom_pairs.extend(parse_bonded_atom_pairs(current_name, id_list))
            sequences.append({"ligand": {"id": id_list, "ccdCodes": ccdCodes}})
        elif sequence_type == "smile":
            sequences.append(
                {
                    "ligand": {
                        "id": id_list,
                        "smiles": "".join(current_sequence).replace(" ", ""),
                    }
                }
            )

    # Create the JSON structure
    data = {
        "name": json_name,  # Use the base name of the input file
        "modelSeeds": [1],
        "sequences": sequences,
        "bondedAtomPairs": bonded_atom_pairs,
        "dialect": "alphafold3",
        "version": 1,
    }

    # Write to JSON file
    with open(json_file, "w", encoding="utf-8") as json_out:
        json.dump(data, json_out, indent=2)
    print(f"\nConversion complete. JSON file saved as {json_file}")


# Check if the script is executed with a FASTA file as input
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <fasta_file>")
        sys.exit(1)

    fasta_file = sys.argv[1]
    if not os.path.exists(fasta_file):
        print(f"Error: File '{fasta_file}' not found.")
        sys.exit(1)

    fasta_to_json(fasta_file)
