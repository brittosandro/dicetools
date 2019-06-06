"""
Receives a Gaussian's ".log" of a scan generated by plot_eff_tors, the generated .dfr,
.txt and atoms defining the dihedral to fit the classical curve to the one from the .log.

Author: Henrique Musseli Cezar
Date: MAY/2019
"""

import argparse
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import openbabel
import pybel
from numpy import cos
from math import ceil
from scipy import optimize
from scipy.interpolate import CubicSpline
from plot_en_angle_gaussian_scan import parse_en_log_gaussian
from plot_eff_tors import *

def species_coord_to_openbabel(species, coord):
  mol = openbabel.OBMol()
  
  # add atoms to mol
  for i, atomSp in species.items():
    a = mol.NewAtom()
    a.SetAtomicNum(int(atomSp))
    a.SetVector(*coord[i])

  # perceive bond information
  mol.ConnectTheDots()
  mol.PerceiveBondOrders()

  return mol


def equal_parameters(dihedrals, mol, tolerance, usevalence):
  infoAtom = []
  dihAngles = []
  for dih in dihedrals:
    acoords = [[mol.GetAtomById(x-1).GetX(),mol.GetAtomById(x-1).GetY(),mol.GetAtomById(x-1).GetZ()] for x in dih]
    dihAngles.append(get_phi(*acoords))
    a1 = mol.GetAtomById(dih[0]-1)
    a4 = mol.GetAtomById(dih[3]-1)
    if usevalence:
      infoAtom.append([a1.GetAtomicNum(), a1.GetValence(), a1.GetHyb(), a4.GetAtomicNum(), a4.GetValence(), a4.GetHyb()])
    else:
      infoAtom.append([a1.GetAtomicNum(), a1.GetHyb(), a4.GetAtomicNum(), a4.GetHyb()])

  equals = []
  for i, pair1 in enumerate(infoAtom):
    # compare to all others
    for j, pair2 in enumerate(infoAtom):
      if j <= i: continue

      pair3 = pair2[int(len(pair2)/2):]+pair2[:int(len(pair2)/2)]

      if (pair1 == pair2) or (pair1 == pair3):
        equals.append([i,j])

  # compare angles to check if dihedrals are really equal
  clean_pairs = []
  for pair in equals:
    ang1 = abs(round(dihAngles[pair[0]],4))
    ang2 = abs(round(dihAngles[pair[1]],4))
    if abs(ang1-ang2) <= tolerance:
      clean_pairs.append(pair)

  return clean_pairs


def torsen_opls(phi, V1, V2, V3, f1, f2, f3):
  return 0.5 * (V1*(1.+cos(phi+f1)) + V2*(1.-cos(2.*phi+f2)) + V3*(1.+cos(3.*phi+f3)))


def torsen_amber(phi, V1, V2, V3, f1, f2, f3):
  return 0.5 * (V1*(1.+cos(phi-f1)) + V2*(1.+cos(2.*phi-f2)) + V3*(1.+cos(3.*phi-f3)))


# thanks to https://stackoverflow.com/a/34226673
def fit_func(phi, *args):
  # first half are vs
  vs = args[:int(len(args)/2)]
  # second half are fs
  fs = args[int(len(args)/2):]
  nfunc = int(len(args)/6)
  sumf = 0.
  for i in range(nfunc):
    sumf += torsen_opls(phi,*vs[3*i:3*(i+1)],*fs[3*i:3*(i+1)])
  return sumf


def fit_func_equals(phi, nequal, *args):
  # first half are vs
  vs = args[:int((len(args)-nequal+1)/2)]
  # second half are fs
  fs = args[int((len(args)-nequal+1)/2):len(args)-nequal+1]
  # identification of equal parameters
  equal = args[len(args)-nequal+1:][0]

  nfunc = int(len(vs)/3)
  sumf = 0.
  for i in range(nfunc):
    calc = False
    for pair in equal:
      if i == pair[1]:
        sumf += torsen_opls(phi,*vs[3*pair[0]:3*(pair[0]+1)],*fs[3*i:3*(i+1)])
        calc = True
    if not calc:
      sumf += torsen_opls(phi,*vs[3*i:3*(i+1)],*fs[3*i:3*(i+1)])

  return sumf


def shift_angle_rad(tetha):
  if tetha < 0.0:
    return tetha
  elif tetha >= np.pi:
    return tetha-(2.*np.pi)
  else:
    return tetha


def write_dfr(dfrfile, dihedrals, params, amber):
  with open(dfrfile, "r") as f:
    line = f.readline()

    while "$dihedral" not in line:
      print(line,end='')
      line = f.readline()

    print(line,end='')
    line = f.readline()
    
    dnum = 1
    pdied = 0
    while "$end dihedral" not in line:
      if dnum in dihedrals:
        # write the fitted parameters
        if amber:
          print("%d %d %d %d\t\tAMBER\t%.3f\t%.3f\t%.3f\t0.0\t0.0\t0.0" % (*dihedrals[dnum][:4], *params[3*pdied:3*(pdied+1)]))
        else:
          print("%d %d %d %d\t\tOPLS\t%.3f\t%.3f\t%.3f\t0.0\t0.0\t0.0" % (*dihedrals[dnum][:4], *params[3*pdied:3*(pdied+1)]))
        pdied += 1
      else:
        print(line,end='')

      dnum += 1
      line = f.readline()

    print(line,end='')
    for line in f:
      print(line,end='')


def find_nearest_idx(array, value):
    array = np.asarray(array)
    closest = (np.abs(array - value)).argmin()
    # check if neighbor is smaller
    if (closest != 0 and closest != len(array)-1):
      if array[closest] > array[closest-1]:
        idx = closest-1
      elif array[closest] > array[closest+1]:
        idx = closest+1
      else:
        idx = closest
    else:
      idx = closest
    return idx


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Receives a Gaussians ".log" of a scan generated by plot_eff_tors, the generated .dfr, .txt and atoms defining the dihedral to fit the classical curve to the one from the .log.')
  parser.add_argument("logfile", help="Gaussian's .log file")
  parser.add_argument("dfrfile", help=".dfr containing current parameters")
  parser.add_argument("txtfile", help=".txt containing the geometry and nonbonded parameters")
  parser.add_argument("a1", type=int, help="first atom defining the reference dihedral")
  parser.add_argument("a2", type=int, help="second atom defining the reference dihedral")
  parser.add_argument("a3", type=int, help="third atom defining the reference dihedral")
  parser.add_argument("a4", type=int, help="fourth atom defining the reference dihedral")
  parser.add_argument("--amber", help="use AMBER rule to 1-4 interactions and torsional energy", action="store_true")
  parser.add_argument("--no-force-min", help="disable the bigger weight given to the minimum points by default", action="store_true")
  parser.add_argument("--plot-minimums", help="plot the interpolated curve and the minimums that were found", action="store_true")
  parser.add_argument("--fit-to-spline", help="use the cubic spline curve for the fit instead of just the few points", action="store_true")
  parser.add_argument("--use-valence", help="also use valence of the atoms when finding similar dihedrals", action="store_true")
  parser.add_argument("--tolerance-dihedral", type=float, help="tolarance value for which dihedral angles are considered to be equal (default = 0.1 radians)", default=0.1)
  parser.add_argument("--bound-values", type=float, help="upper and lower bound [-val,+val] for the fitted parameters (default = 5)", default=5.)
  parser.add_argument("--cut-energy", type=float, help="the percentage of highest energies that should not be considered during the fit (default = 0.3)", default=0.3)
  args = parser.parse_args()

  # parse data from the log file
  died, enqm = parse_en_log_gaussian(args.logfile)
  died = [shift_angle_rad(x*np.pi/180.) for x in died]

  # parse dfr to get the dihedrals involved in the rotation
  dihedralsDict, connInfo, fragInfo, fconnInfo = parse_dfr(args.dfrfile, args.a2, args.a3)

  # parse txt to get geometry
  _, natoms, atomSp, atomsCoord, _ = parse_txt(args.txtfile)
  mol = species_coord_to_openbabel(atomSp, atomsCoord)

  # get dihedrals which should have the same parameters
  equals = equal_parameters([dihedralsDict[x][:4] for x in dihedralsDict], mol, args.tolerance_dihedral, args.use_valence)

  # get reference angle
  acoords = [atomsCoord[x] for x in [args.a1, args.a2, args.a3, args.a4]]
  ref_ang = get_phi(*acoords)

  # get initial dihedral angles for each torsional involved in the rotation
  dihAngles = []
  for tors in dihedralsDict:
    acoords = [atomsCoord[x] for x in dihedralsDict[tors][:4]]
    dihAngles.append(get_phi(*acoords)-ref_ang)

  # get the classical curve with current parameters
  diedClass, _, nben, _ =  get_potential_curve(args.txtfile, args.dfrfile, args.a1, args.a2, args.a3, args.a4, len(died), "", False, args.amber, False, False)
  # convert the angles and sort
  diedClass = [shift_angle_rad(x) for x in diedClass]
  diedClass, nben = (list(t) for t in zip(*sorted(zip(diedClass, nben))))

  # plotting options
  mpl.rcParams.update({'font.size':12, 'text.usetex':True, 'font.family':'serif', 'ytick.major.pad':4})

  # prepare the data
  v0s = []
  f0s = []
  for i, dih in enumerate(dihedralsDict):
    v0s += dihedralsDict[dih][4:7]
    f0s += [dihAngles[i], 2.*dihAngles[i], 3.*dihAngles[i]]

  # set the bounds
  lbound = len(v0s)*[-args.bound_values]
  ubound = len(v0s)*[args.bound_values]

  # shift the energies to the same reference
  min_mq = min(enqm)
  enqm = [x-min_mq for x in enqm]
  min_class = nben[np.argmin(enqm)] # set as zero the same angle used before for QM
  nben = [x-min_class for x in nben]
  died = np.asarray(died)
  enqm = np.asarray(enqm)
  nben = np.asarray(nben)

  # subtract the nonbonded energy to get the "QM torsional"
  enfit = enqm - nben

  # Get the minimums of the enqm curve
  # set the initial and final points to have the same (lowest) energy
  if enqm[len(enqm)-1] != enqm[0]:
    # if maximum
    if enqm[len(enqm)-1]-enqm[len(enqm)-2] > 0:
      if enqm[len(enqm)-1] > enqm[0]:
        died_spline = np.insert(died, 0, -died[len(died)-1])
        en_spline = np.insert(enqm, 0, enqm[len(enqm)-1])
      else:
        died_spline = np.append(died, -died[0])
        en_spline = np.append(enqm, enqm[0])
    # if minimum
    else:
      if enqm[len(enqm)-1] < enqm[0]:
        died_spline = np.insert(died, 0, -died[len(died)-1])
        en_spline = np.insert(enqm, 0, enqm[len(enqm)-1])
      else:
        died_spline = np.append(died, -died[0])
        en_spline = np.append(enqm, enqm[0])
  else:
    died_spline = died
    en_spline = enqm

  # set the boundaries for enfit too
  died_enfit_spline = died
  if enfit[len(enfit)-1] != enfit[0]:
    if abs(died[0]) != abs(died[len(died)-1]):
      # if maximum
      if enfit[len(enfit)-1]-enfit[len(enfit)-2] > 0:
        if enfit[len(enfit)-1] > enfit[0]:
          died_enfit_spline = np.insert(died, 0, -died[len(died)-1])
          enfit_spline = np.insert(enfit, 0, enfit[len(enfit)-1])
        else:
          died_enfit_spline = np.append(died, -died[0])
          enfit_spline = np.append(enfit, enfit[0])
      # if minimum
      else:
        if enfit[len(enfit)-1] < enfit[0]:
          died_enfit_spline = np.insert(died, 0, -died[len(died)-1])
          enfit_spline = np.insert(enfit, 0, enfit[len(enfit)-1])
        else:
          died_enfit_spline = np.append(died, -died[0])
          enfit_spline = np.append(enfit, enfit[0])
    else:
      print("entrei")
      extremes = [enfit[0], enfit[len(enfit)-1]]
      enfit_spline = enfit
      enfit_spline[0] = min(extremes)
      enfit_spline[len(enfit_spline)-1] = min(extremes)
  else:
    enfit_spline = enfit


  f = CubicSpline(died_spline, en_spline, bc_type='periodic')
  ffit = CubicSpline(died_enfit_spline, enfit_spline, bc_type='periodic')
  cr_pts = f.derivative().roots()
  deriv2 = f.derivative(2)
  cr_pts = np.delete(cr_pts, np.where(deriv2(cr_pts) < 0.))
  xc = np.arange(-3.142,3.142, 0.02)

  # plot the spline and minimums
  if args.plot_minimums:
    plt.plot(xc, f(xc), label='Cubic spline')
    plt.plot(cr_pts, f(cr_pts), 'o', label="Minima")
    plt.legend()
    plt.xlabel(r"$\phi$ (radians)")
    plt.ylabel(r"$E$ (kcal/mol)")
    plt.xlim([-3.142,3.142])
    plt.show()

  # order and remove the points relative to the transition states
  npremove = ceil(args.cut_energy*len(died))
  lowenremove = -np.sort(-enfit)[npremove-1]
  filtbar = np.where(enfit >= lowenremove)

  olddied = died
  died = np.delete(died, filtbar)
  enfit = np.delete(enfit, filtbar)

  if not args.fit_to_spline:
    # give greater weight to minimums (smaller sigma is a grater weight)
    weights = np.ones(len(died))
    if not args.no_force_min:
      idx_min = []
      for val in cr_pts:
        idx_min.append(find_nearest_idx(died,val))
      weights[idx_min] = 0.1

    if equals:
      popt, pcov = optimize.curve_fit(lambda x, *vs: fit_func_equals(x, len(equals), *vs, *f0s, equals), died, enfit, p0=v0s, bounds=(lbound,ubound), sigma=weights)
    else:
      popt, pcov = optimize.curve_fit(lambda x, *vs: fit_func(x, *vs, *f0s), died, enfit, p0=v0s, bounds=(lbound,ubound), sigma=weights)
  else:
    # give greater weight to minimums (smaller sigma is a grater weight)
    weights = np.ones(len(xc))
    if not args.no_force_min:
      idx_min = []
      for val in cr_pts:
        idx_min.append(find_nearest_idx(died,val))
      weights[idx_min] = 0.1

    if equals:
      popt, pcov = optimize.curve_fit(lambda x, *vs: fit_func_equals(x, len(equals), *vs, *f0s, equals), xc, ffit(xc), p0=v0s, bounds=(lbound,ubound), sigma=weights)
    else:
      popt, pcov = optimize.curve_fit(lambda x, *vs: fit_func(x, *vs, *f0s), xc, ffit(xc), p0=v0s, bounds=(lbound,ubound), sigma=weights)


  if equals:
    new_popt = []
    for tors in range(int(len(popt)/3)):
      fnd = False
      for pair in equals:
        if tors == pair[1]:
          new_popt += [round(x,3) for x in popt[pair[0]*3:3*(pair[0]+1)]]
          fnd = True
      if not fnd:
        new_popt += [round(x,3) for x in popt[tors*3:3*(tors+1)]]
    popt = np.asarray(new_popt)
  else:
    popt = [round(x,3) for x in popt]

  # plot the curves to compare
  fcurv = []
  for val in olddied:
    fcurv.append(fit_func(val,*popt,*f0s))

  # write the adjusted dfr
  write_dfr(args.dfrfile, dihedralsDict, popt, args.amber)

  plt.plot(olddied, enqm, label='Gaussian total energy')
  plt.plot(olddied, nben, label='Classical nonbonded energy')
  plt.plot(died, enfit, label='Gaussian torsional energy')
  plt.plot(olddied, fcurv, label='Fit')
  plt.plot(olddied, fcurv+nben, label='Classical total energy')
  plt.legend()
  plt.xlabel(r"$\phi$ (radians)")
  plt.ylabel(r"$E$ (kcal/mol)")
  plt.show()