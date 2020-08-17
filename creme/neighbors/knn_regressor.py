import numpy as np

from creme import base
from creme.utils import dict2numpy

from .base_neighbors import BaseNeighbors


class KNNRegressor(BaseNeighbors, base.Regressor):
    """k-Nearest Neighbors regressor.

    This non-parametric regression method keeps track of the last
    `max_window_size` training samples. Predictions are obtained by
    aggregating the values of the closest n_neighbors stored-samples with
    respect to a query sample.

    Parameters
    ----------
    n_neighbors : int (default=5)
        The number of nearest neighbors to search for.

    max_window_size : int (default=1000)
        The maximum size of the window storing the last observed samples.

    leaf_size : int (default=30)
        scipy.spatial.cKDTree parameter. The maximum number of samples that
        can be stored in one leaf node, which determines from which point
        the algorithm will switch for a brute-force approach. The bigger
        this number the faster the tree construction time, but the slower
        the query time will be.

    p : float (default=2)
        p-norm value for the Minkowski metric. When `p=1`, this corresponds to the
        Manhattan distance, while `p=2` corresponds to the Euclidean distance. Valid
        values are in the interval $[1, +\infty)$

    aggregation_method : str (default='mean')
            | The method to aggregate the target values of neighbors.
            | 'mean'
            | 'median'
            | 'weighted_mean'

    Notes
    -----
    This estimator is not optimal for a mixture of categorical and numerical
    features. This implementation treats all features from a given stream as
    numerical.

    Examples
    --------
    >>> from creme import datasets
    >>> from creme import evaluate
    >>> from creme import metrics
    >>> from creme import neighbors
    >>> from creme import preprocessing

    >>> dataset = datasets.TrumpApproval()

    >>> model = (
    ...  preprocessing.StandardScaler() |
    ...  neighbors.KNNRegressor(max_window_size=50)
    ... )

    >>> metric = metrics.MAE()

    >>> evaluate.progressive_val_score(dataset, model, metric)
    # MAE: 0.399144

    """

    _MEAN = 'mean'
    _MEDIAN = 'median'
    _WEIGHTED_MEAN = 'weighted_mean'

    def __init__(self, n_neighbors: int = 5, max_window_size: int = 1000, leaf_size: int = 30,
                 p: float = 2, aggregation_method: str = 'mean'):

        super().__init__(n_neighbors=n_neighbors,
                         max_window_size=max_window_size,
                         leaf_size=leaf_size,
                         p=p)
        if aggregation_method not in {self._MEAN, self._MEDIAN, self._WEIGHTED_MEAN}:
            raise ValueError('Invalid aggregation_method: {}.\n'
                             'Valid options are: {}'.format(aggregation_method,
                                                            {self._MEAN, self._MEDIAN,
                                                             self.f_WEIGHTED_MEAN}))
        self.aggregation_method = aggregation_method

    def learn_one(self, x: dict, y: base.typing.RegTarget) -> 'Regressor':
        """Fits to a set of features ``x`` and a real-valued target ``y``.

        Parameters
        ----------
            x: A dictionary of features.
            y: A numeric target.

        Returns
        -------
            self

        Notes
        -----
        For the K-Nearest Neighbors regressor, fitting the model is the
        equivalent of inserting the newer samples in the observed window,
        and if the `max_window_size` is reached, removing older results.

        """

        x_arr = dict2numpy(x)
        self.data_window.add_one(x_arr, y)

        return self

    def predict_one(self, x: dict) -> base.typing.RegTarget:
        """Predicts the target value of a set of features `x`.

        Search the KDTree for the `n_neighbors` nearest neighbors.

        Parameters
        ----------
            x : A dictionary of features.

        Returns
        -------
            The prediction.

        """

        if self.data_window is None or self.data_window.size < self.n_neighbors:
            # Not enough information available, return default prediction
            return None

        x_arr = dict2numpy(x)

        dists, neighbor_idx = self._get_neighbors(x_arr)
        target_buffer = self.data_window.targets_buffer

        neighbor_vals = []

        for index in neighbor_idx[0]:
            neighbor_vals.append(target_buffer[index])

        if self.aggregation_method == self._MEAN:
            y_pred = np.mean(neighbor_vals)
        elif self.aggregation_method == self._MEDIAN:
            y_pred = np.median(neighbor_vals)
        else:  # weighted mean
            sum_dist = dists.sum()
            weights = np.array([1. - dist / sum_dist for dist in dists[0]])
            # Weights are proportional to the inverse of the distance
            weights /= weights.sum()

            y_pred = np.average(neighbor_vals, weights=weights)

        return y_pred
