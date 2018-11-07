"""
Receives a complete .dfr (generated by either fragGen or gromacs2dice)
and based on the 'atoms fragments' section, remove unecessary degrees
of freedom from the input.

Author: Henrique Musseli Cezar
Date: SEP/2016
"""

import os
import argparse

def clean_dofs(fname):
  with open(fname,'r') as f:
    # read lines until it gets to 'atoms fragments'
    line = f.readline()
    while line.strip() != '$atoms fragments':
      line = f.readline()

    # read fragments and store the rigid ones
    frags = {}
    rigidFrags = []
    line = f.readline()
    while '$end' not in line.strip():
      if not line.strip():
        line = f.readline()
        continue
      frags[int(line.split()[0])] = [int(x) for x in line.split()[1:-1]]
      frags[int(line.split()[0])].append(line.split()[-1])
      if frags[int(line.split()[0])][-1].upper() == 'R': 
        rigidFrags.append(int(line.split()[0]))
      line = f.readline()
    nfrags = len(frags.keys())

    # get the fragment connections
    fConnLines = []
    line = f.readline()
    while line.strip() != '$fragment connection':
      line = f.readline()
    line = f.readline()
    while '$end' not in line.strip():
      if not line.strip():
        line = f.readline()
        continue
      fConnLines.append(line)
      line = f.readline()

    # start removing the dofs
    
    # remove every unused bond
    # bonds = []
    # line = f.readline()
    # while line.strip() != '$bond':
    #   line = f.readline()
    # line = f.readline()
    # while '$end' not in line.strip():
    #   if not line.strip():
    #     line = f.readline()
    #     continue
    #   save = True
    #   a1, a2 = [int(x) for x in line.split()[:2]]
    #   for rig in rigidFrags:
    #     if (a1 in frags[rig]) and (a2 in frags[rig]):
    #       save = False
    #   if save:
    #     bonds.append(line)
    #   line = f.readline()

    # just append all bonds, since they are used to determine the fnb in DICE
    bonds = []
    line = f.readline()
    while line.strip() != '$bond':
      line = f.readline()
    line = f.readline()
    while '$end' not in line.strip():
      if not line.strip():
        line = f.readline()
        continue    
      bonds.append(line)
      line = f.readline()

    # remove every unused angle
    angles = []
    line = f.readline()
    while line.strip() != '$angle':
      line = f.readline()
    line = f.readline()
    while '$end' not in line.strip():
      if not line.strip():
        line = f.readline()
        continue
      save = True
      a1, a2, a3 = [int(x) for x in line.split()[:3]]
      for rig in rigidFrags:
        if (a1 in frags[rig]) and (a2 in frags[rig]) and (a3 in frags[rig]):
          save = False
      if save:
        angles.append(line)
      line = f.readline()

    # remove every unused dihedral
    dihedrals = []
    line = f.readline()
    while line.strip() != '$dihedral':
      line = f.readline()
    line = f.readline()
    while '$end' not in line.strip():
      if not line.strip():
        line = f.readline()
        continue
      save = True
      a1, a2, a3, a4 = [int(x) for x in line.split()[:4]]
      for rig in rigidFrags:
        if (a1 in frags[rig]) and (a2 in frags[rig]) and (a3 in frags[rig]) and (a4 in frags[rig]):
          save = False
      if save:
        dihedrals.append(line)
      line = f.readline()

    # remove every unused improper dihedral
    imp_dihedrals = []
    line = f.readline()
    impd = True
    while line.strip() != '$improper dihedral':
      line = f.readline()
      if line == '':
        impd = False
        break
    if impd:
      line = f.readline()
      while '$end' not in line.strip():
        if not line.strip():
          line = f.readline()
          continue
        save = True
        a1, a2, a3, a4 = [int(x) for x in line.split()[:4]]
        for rig in rigidFrags:
          if (a1 in frags[rig]) and (a2 in frags[rig]) and (a3 in frags[rig]) and (a4 in frags[rig]):
            save = False
        if save:
          imp_dihedrals.append(line)
        line = f.readline()

    # print the simplified dfr to screen
    print('$atoms fragments')
    for frag in frags.keys():
      string = ""
      string += str(frag)+"\t"
      for el in frags[frag]:
        string += str(el)+"\t"
      print(string)
    print('$end atoms fragments\n')

    print('$fragment connection')
    for line in fConnLines:
      print("%s" % line.strip())
    print('$end fragment connection\n')

    print('$bond')
    for line in bonds:
      print("%s" % line.strip())
    print('$end bond\n')

    if len(angles) > 0:
      print('$angle')
      for line in angles:
        print("%s" % line.strip())
      print('$end angle\n')

    print('$dihedral')
    for line in dihedrals:
      print("%s" % line.strip())
    print('$end dihedral\n')

    if (len(imp_dihedrals) > 0) and impd:
      print('$improper dihedral')
      for line in imp_dihedrals:
        print("%s" % line.strip())
      print('$end improper dihedral\n')


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Receives a complete .dfr (generated by either fragGen or gromacs2dice) and based on the 'atoms fragments' section, remove unecessary degrees of freedom from the input.")
  parser.add_argument("filename", help="the dfr containing all the degrees of freedom information")
  args = parser.parse_args()

  filename = os.path.realpath(args.filename)
  base, ext = os.path.splitext(filename)

  clean_dofs(filename)