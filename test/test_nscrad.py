import unittest
from radmap import nscrad
import numpy as np

class TestSCR(unittest.TestCase):
    def test_sum_histograms(self):
        for i in range(100):
            hists = np.random.random_integers(100, size=(10,4096))
            self.assertEquals(sum(nscrad.sumHistograms(hists)), np.sum(hists))

    def test_downsample(self):
        """Test that downsampled histograms are done as we'd expect."""
        samples = [{"hist": [1, 3, 6, 2, 6, 8, 2, 7, 9, 1], "bins": [(0, 2), (0, 3), (0, 10)],
                    "counts": [4, 10, 45]},
                   {"hist": [1, 2, -10], "bins": [(0, 1), (0, 2), (1, 3)],
                    "counts": [1, 3, -8]},
                   {"hist": [1, 2, 3, 4, 5, 6, 7, 8, 9], "bins": [(0, 20)],
                    "counts": [45]}]

        for sample in samples:
            downsampled = nscrad.downsampleHistogram(sample["hist"], sample["bins"])
            self.assertTrue(np.array_equal(downsampled, sample["counts"]),
                            msg="Downsample error: got %s, expected %s" % (str(downsampled), str(sample["counts"])))

    def test_shape_matrix(self):
        # If any bin is zero, it should be clipped to 1
        hist = [1., 2., 3., 4., 0.]
        result = np.array([[1, -1/2., 0, 0, 0],
                           [1, 0, -1/3., 0, 0],
                           [1, 0, 0, -1/4., 0],
                           [1, 0, 0, 0, -1/1.]])
        self.assertTrue(np.array_equal(result, nscrad.getShapeMatrix(hist)))

if __name__ == "__main__":
    unittest.main()
