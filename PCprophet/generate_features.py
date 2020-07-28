import re
import sys
import os
import numpy as np
import scipy.signal as signal
import pandas as pd
from scipy.ndimage import uniform_filter

import PCprophet.parse_go as go
import PCprophet.io_ as io
import PCprophet.stats_ as st


class ProteinProfile(object):
    """
    docstring for ProteinProfile
    """

    def __init__(self, acc, inten):
        super(ProteinProfile, self).__init__()
        self.acc = acc
        self.inten = np.array([float(x) for x in inten])
        self.peaks = []

    def get_inte(self):
        return self.inten

    def get_acc(self):
        return self.acc

    def get_peaks(self):
        return self.peaks

    @io.timeit
    def calc_peaks(self):
        pks = list(st.peak_picking(self.inten)[0])
        # avoid breakage due to float
        self.peaks = [int(x) for x in pks]


class ComplexProfile(object):
    """
    docstring for ComplexProfile
    formed by a list of ProteinProfile
    """

    def __init__(self, name):
        super(ComplexProfile, self).__init__()
        self.name = name
        self.goscore = 0
        # members needs to be reformat to have a 2d matrix
        self.members = []
        self.pks = {}
        self.width = {}
        self.shifts = []
        self.cor = []
        self.diff = []
        self.pks_ali = []

    def test_complex(self):
        if len(self.members) < 2 or len(self.members) > 100:
            return False
        else:
            return True

    def add_member(self, prot):
        self.members.append(prot)

    def get_members(self):
        return [x.get_acc() for x in self.members]

    def get_name(self):
        return self.name

    def create_matrix(self):
        """
        create numpy 2d array for vectorization
        """
        arr = [x.get_inte() for x in self.members]
        return np.array(arr)

    def get_peaks(self):
        """
        yields one formatted row with pks sel and id
        """
        for k in self.pks.keys():
            yield "{}\t{}\t{}".format(k, self.get_name(), self.pks[k])

    @io.timeit
    def calc_go_score(self, goobj, gaf):
        self.score = go.combine_all(goobj, gaf, np.array(self.get_members()),)

    def format_ids(self):
        """
        create a complex identifier by contatenating all the acc
        """
        cmplx_members = self.get_members()
        return "#".join(cmplx_members)

    @io.timeit
    def calc_corr(self, pairs, W=10):
        """
        vectorized correlation between pairs vectors with sliding window
        """
        a, b = pairs[0].get_inte(), pairs[1].get_inte()
        # a,b are input arrays; W is window length

        am = uniform_filter(a.astype(float), W)
        bm = uniform_filter(b.astype(float), W)

        amc = am[W // 2: -W // 2 + 1]
        bmc = bm[W // 2: -W // 2 + 1]

        da = a[:, None] - amc
        db = b[:, None] - bmc

        # Get sliding mask of valid windows
        m, n = da.shape
        mask1 = np.arange(m)[:, None] >= np.arange(n)
        mask2 = np.arange(m)[:, None] < np.arange(n) + W
        mask = mask1 & mask2
        dam = da * mask
        dbm = db * mask

        ssAs = np.einsum("ij,ij->j", dam, dam)
        ssBs = np.einsum("ij,ij->j", dbm, dbm)
        D = np.einsum("ij,ij->j", dam, dbm)
        # add np.nan to reach 72
        self.cor.append(np.hstack((D / np.sqrt(ssAs * ssBs), np.zeros(9) + np.nan)))

    @io.timeit
    def align_peaks(self):
        """
        align all protein peaks
        """
        # now we need to create the align file for each protein in this cmplx
        pk = [prot.get_peaks() for prot in self.members]
        idx_missing = [i for i, j in enumerate(pk) if not j]
        nan_members = [self.get_members()[i] for i in idx_missing]
        pres = [x for x in pk if x]
        mb_pres = [x for x in self.get_members() if x not in nan_members]
        if nan_members == self.get_members():
            self.pks_ali = dict(zip(nan_members, [np.nan] * len(nan_members)))
            return None
        else:
            ali_pk = alligner(pres)
            md = round(st.medi(ali_pk))
            # missing values gets the median of aligned peaks
            self.pks_ali = dict(zip(nan_members, [md] * len(nan_members)))
            self.pks_ali.update(dict(zip(mb_pres, ali_pk)))
            for k in self.members:
                if k.get_peaks():
                    _ = "#".join(map(str, k.get_peaks()))
                else:
                    _ = str(self.pks_ali[k.get_acc()])
                pks = _ + "\t" + str(self.pks_ali[k.get_acc()])
                self.pks[k.get_acc()] = pks
            return True

    def pairwise(self):
        """
        performs pairwise comparison
        """
        for pairs in st.fast_comb(np.array(self.members), 2):
            self.calc_corr(pairs)
            self.calc_diff(*pairs)
            self.calc_shift([x.get_acc() for x in pairs])
        # now need to average
        self.cor = np.mean(self.cor, axis=0)
        self.diff = np.mean(self.diff, axis=0)
        self.shifts = np.mean(self.shifts)

    def calc_shift(self, ids):
        self.shifts.append(abs(self.pks_ali[ids[0]] - self.pks_ali[ids[1]]))

    def calc_diff(self, p1, p2):
        self.diff.append(abs(p1.get_inte() - p2.get_inte()))

    @io.timeit
    def calc_width(self):
        q = 5
        width = []
        for prot in self.members:
            peak = int(self.pks_ali[prot.get_acc()])
            prot_peak = prot.get_inte()[(peak - q): (peak + q)]
            prot_fwhm = st.fwhm(list(prot_peak))
            width.append(prot_fwhm)
        self.width = np.mean(width)

    def create_row(self):
        """
        get all outputs and create a row
        """
        dif_conc = ",".join([str(x) for x in self.diff])
        cor_conc = ",".join([str(x) for x in self.cor])
        row_id = self.get_name()
        members = self.format_ids()
        row = [
            row_id,
            members,
            cor_conc,
            str(self.shifts),
            dif_conc,
            str(self.width),
            self.score,
        ]
        return "\t".join([str(x) for x in row])


def add_top(result, item):
    """Inserts item into list of results"""
    length = len(result)
    index = 0
    # if less than lenght and better diff
    while index < length and result[index][1] < item[1]:
        index += 1
    result.insert(index, item)


def minimize(solution):
    """Returns total difference of solution passed """
    length = len(solution)
    result = 0
    for index, number1 in enumerate(solution):
        for nr_2_indx in range(index + 1, length):
            result += abs(number1 - solution[nr_2_indx])
    return result


def min_sd(aoa):
    rf_pk = []
    for v in aoa:
        rf_pk.append([x for x in v if x is not None])
    ln = max([len(x) for x in rf_pk])
    rf_pk2 = [x[:ln] for x in rf_pk]
    for short in rf_pk2:
        while len(short) < ln:
            try:
                short.append(short[-1])
            except IndexError as e:
                break
    pkn = pd.DataFrame(rf_pk2)
    # now all peaks detected are alligned rowise
    # calc standard deviation and take index of min sd
    sd = (pkn.apply(lambda col: np.std(col, ddof=1), axis=0)).tolist()
    try:
        sd = sd.index(min(sd))
    except ValueError as e:
        return None
    indx = []
    # for each protein append index of peak
    # input is protA [peak, peak ,peak]
    # indx out is [protA=> peak, protB => peak, protC => peak]
    # order is same because we append from same array
    for mx_indx in rf_pk2:
        try:
            indx.append(mx_indx[sd])
        # if no peak in mx_indx append none
        except IndexError as e:
            indx.append(None)
    return indx


def shortest_path(aoa, max_trial=5000):
    elements = len(aoa)
    result = [[[x], 0] for x in aoa[0]]
    trial = 1
    while True:
        if trial == max_trial:
            return None
        trial += 1
        sol = result.pop(0)
        # print(sol)
        # Return the top item if it is complete
        if len(sol[0]) == elements:
            return sol[0]
            # Make new solutions with top item
        for peak in aoa[len(sol[0])]:
            new_pk = [sol[0].copy(), 0]
            new_pk[0].append(peak)
            new_pk[1] = minimize(new_pk[0])
            add_top(result, new_pk)

@io.timeit
def alligner(aoa):
    """Finds closest points of a list of lists"""
    # one of arrays is empty
    for x in aoa:
        if not x:
            return None
    # there is the same nr in all array no need to do anything
    candidate = set.intersection(*map(set, aoa))
    if candidate:
        # returns intersect
        return [max(list(candidate))] * len(aoa)
    else:
        pks = shortest_path(aoa)
        if pks:
            return pks
        else:
            pks = min_sd(aoa)
            return pks


def format_hash(temp):
    """
    get a row hash and create a ComplexProfile object
    """
    inten = temp["FT"].split("#")
    members = temp["MB"].split("#")
    tmp = ComplexProfile(temp["ID"])
    for idx, acc in enumerate(members):
        if acc in tmp.get_members():
            continue
        # peak picking already here
        protein = ProteinProfile(acc, inten[idx].split(","))
        protein.calc_peaks()
        tmp.add_member(protein)
    return tmp


def gen_feat(cmplx, goobj, gaf):
    """
    receive a single row and generate feature calc
    """
    if cmplx.test_complex() and cmplx.align_peaks():
        cmplx.calc_go_score(goobj, gaf)
        cmplx.calc_width()
        cmplx.pairwise()
        return cmplx.create_row(), cmplx.get_peaks()
    else:
        return None, None


# wrapper
def mp_cmplx(filename, goobj, gaf):
    """
    map complex into 3 vector => cor vectors
    shift peak
    width peak
    w = point for correlation
    cor(A[idx:(idx + w)], B[idx:(idx+w)])
    width = fwhm(A[idx-q:idx+q])
    so q should be 1/2 of w ?
    """
    things, header = [], []
    temp = {}
    feat_file = []
    peaks_file = []
    print("calculating features for " + filename)
    for line in open(filename, "r"):
        line = line.rstrip("\n")
        if line.startswith("ID" + "\t"):
            header = re.split(r"\t+", line)
        else:
            things = re.split(r"\t+", line)
            temp = {}
            temp = dict(zip(header, things))
        if temp:
            cmplx = format_hash(temp)
            feat_row, peaks = gen_feat(cmplx, goobj, gaf)
            if feat_row and peaks:
                feat_file.append(feat_row)
                [peaks_file.append(x) for x in list(peaks)]
    return feat_file, peaks_file


def runner(base, go_obo, tsp_go):
    """
    generate all features from the mapped complexes file
    base = config[GLOBAL][TEMP]filename
    """
    go_tree = go.from_obo(io.resource_path(go_obo))
    gaf = go.read_gaf_out(io.resource_path(tsp_go))
    # get tmp/filename folder
    cmplx_comb = os.path.join(base, "cmplx_combined.txt")
    # print(os.path.dirname(os.path.realpath(__file__)))
    wr, pks = mp_cmplx(filename=cmplx_comb, goobj=go_tree, gaf=gaf)
    feature_path = os.path.join(base, "mp_feat_norm.txt")
    feat_header = [
        "ID",
        "MB",
        "COR",
        "SHFT",
        "DIF",
        "W",
        "SC_CC",
        "SC_MF",
        "SC_BP",
        "TOTS",
    ]
    io.wrout(wr, feature_path, feat_header)
    peaklist_path = os.path.join(base, "peak_list.txt")
    # peaklist_path = peaklist_path
    io.wrout(pks, peaklist_path, ["MB", "ID", "PKS", "SEL"])
