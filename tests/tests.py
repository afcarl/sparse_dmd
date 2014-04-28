import numpy.testing as nt

import scipy.io
import numpy as np

import sparse_dmd


def create_snapshots():
    """How to create the reference snapshots."""
    import gc_turbulence as g

    run = g.ProcessedRun(g.default_processed + 'r13_12_16a.hdf5')
    # slice with no nans
    # ( or use # complement(find_nan_slice(run.Uf_[:])) )
    good_slice = (slice(None), slice(None), slice(46L, None))
    data = run.Uf_[good_slice]

    iz, ix, it = data.shape
    snapshots = data.transpose((0, 2, 1)).reshape((-1, ix))

    mat_dict = {'snapshots': snapshots}

    scipy.io.savemat('snapshots.mat', mat_dict)


def create_answer(n=200):
    answer = sparse_dmd.run_dmdsp(gamma_grd=n)
    scipy.io.savemat('tests/answer.mat', answer)


def test_compare_outputs():
    """Compare the python output with the matlab output.
    They should be identical."""
    channel_mat = 'matlab/codes/channel/channel.mat'

    mat_dict = scipy.io.loadmat(channel_mat)

    UstarX1 = mat_dict['UstarX1']
    S = mat_dict['S']
    V = mat_dict['V']

    # Sparsity-promoting parameter gamma
    # Lower and upper bounds relevant for this flow type
    gamma_grd = 20
    gammaval = np.logspace(np.log10(0.15), np.log10(160), gamma_grd)

    Fdmd, Edmd, Ydmd, xdmd, py_answer = sparse_dmd.run_dmdsp(UstarX1,
                                                            S,
                                                            V,
                                                            gammaval)
    # convert class attributes to dict
    py_answer = py_answer.__dict__

    ## matlab output created by running matlab:
    ## [Fdmd, Edmd, Ydmd, xdmd, answer] = run_dmdsp;
    ## output = struct('Fdmd', Fdmd, 'Edmd', Edmd, 'Ydmd', Ydmd, 'xdmd', xdmd);
    ## save('tests/answer.mat', '-struct', 'answer')
    ## save('tests/output.mat', '-struct', 'output')
    ## using channel=1 and 20 gridpoints for gamma

    # using two different .mat because scipy doesn't seem to like
    # nested structs
    mat_answer = scipy.io.loadmat('tests/answer.mat')
    mat_output = scipy.io.loadmat('tests/output.mat')

    for k in py_answer:
        nt.assert_array_almost_equal(py_answer[k].squeeze(),
                                     mat_answer[k].squeeze(),
                                     decimal=5)

    py_output = {'Fdmd': Fdmd, 'Edmd': Edmd, 'Ydmd': Ydmd, 'xdmd': xdmd}

    for k in py_output:
        nt.assert_array_almost_equal(py_output[k].squeeze(),
                                     mat_output[k].squeeze(),
                                     decimal=5)


def test_compare_inputs():
    """Compare UstarX1, V, S generated with my method with those
    calculated with a matlab method.

    Do this with my lab data as don't want to re generate original
    channel.mat data.

    Use python to extract the lab data and format as snapshots. Save
    this as a .mat and use as reference.

    The test then starts using a .mat of snapshots as input and a
    .mat generated by matlab as a known output. The matlab code used
    to generate the matlab output is stored in 'create_reference.m'.
    """
    # load reference snapshots
    snapshots = scipy.io.loadmat('tests/snapshots.mat')['snapshots']

    # compute the python reduction
    py_data = sparse_dmd.SparseDMD.dmd_reduction(snapshots)

    # load reference matlab output
    mat_data = scipy.io.loadmat('tests/reference.mat')

    for k in ('UstarX1', 'S', 'V'):
        nt.assert_array_almost_equal(getattr(py_data, k).squeeze(),
                                     mat_data[k].squeeze(), decimal=3)


def reconstruction():
    """A simple test case for reconstruction of data by DMD.

    A uniform field oscillating at a single frequency should have a
    single uniform dynamic mode corresponding to the frequency.
    """
    t = np.arange(0, 1000)[None]
    # choose set of frequencies well below nyquist and with plenty
    # of samples
    nf = 5
    fi = np.linspace(0.05 + 0.001j, 0.2 + 0.005j, nf)[:, None]

    # set of time series
    ti = np.exp(2j * np.pi * fi * t).real
    time_series = ti

    # random field for each frequency
    fields = np.random.random((50, nf))

    # need time series noise?
    noise = np.random.random(t.shape)

    # the data is the superposition of each field varied through
    # time, permuted by some noise
    time_fields = time_series[..., None] * fields[:, None, ...].T
    superposition = np.sum(time_fields, axis=0) / nf
    data = superposition.T

    # FIXME: this data forms non positive definite P, which can't be
    # fed through cholesky decomp. you can use lu decomp instead,
    # but this worries me as I think P has to be positive definite
    # as each of the elements is a vector product |y_i|^2.|u_i|^2
    # and so is a gram matrix of linearly independent vectors.
    # I think the problem is something to do with the artificial
    # data but I don't really understand.

    # Possibly fixed - problem was not truncating zeros from svd
    # results
    return data

    # don't need to do anything to make snapshots as data already
    # has that form
    dmd = sparse_dmd.SparseDMD(snapshots=data)


def compare_modred_sparse():
    """Compare output from modred with our sparse method."""
    import modred as mr
    import gc_turbulence as g

    run = g.ProcessedRun(g.default_processed + 'r13_12_16a.hdf5')
    # slice with no nans
    # ( or use # complement(find_nan_slice(run.Uf_[:])) )
    good_slice = (slice(None), slice(None), slice(46L, None))
    data = run.Uf_[good_slice]

    snapshots = sparse_dmd.SparseDMD.to_snaps(data, decomp_axis=1)

    modes, ritz_values, norms \
        = mr.compute_DMD_matrices_snaps_method(snapshots, slice(None))

    pmodes, pnorms \
        = mr.compute_POD_matrices_snaps_method(snapshots, slice(None))

    dmd = sparse_dmd.SparseDMD(snapshots)
