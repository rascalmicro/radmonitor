import unittest
from radmap import krige
import numpy as np

class TestKrige(unittest.TestCase):
    def test_krige(self):
        pts = np.array([[0, 1], [2, 1]])
        data = np.transpose(np.array([[5, 1], [1, 5]]))
        times = np.transpose(np.array([[3., 1.,]]))

        pred_points = np.array([[1, 1], [1, 0]])

        preds = np.transpose(np.array([[1.43545, 1.43545], [1.95185, 1.95185]]))
        vars = np.transpose(np.array([[0.549751, 0.894291], [0.549751, 0.894291]]))

        result = krige.krige_at(pts, times, data, pred_points,
                                krige.make_sq_exp(2, 1))

        self.assertTrue(np.allclose(preds, result[0]))
        self.assertTrue(np.allclose(vars, result[1]))

    def test_sq_cov(self):
        cov = krige.make_sq_exp(2, 1)

        self.assertEqual(cov(np.array([0,0]), np.array([0,0])), 1)
        self.assertTrue(np.allclose(cov(np.array([1,0]), np.array([0,0])), 0.778801))

    def test_anomaly(self):
        preds = np.transpose(np.array([[10., 20., 30., 30.]]))
        vars = np.transpose(np.array([[10., 5., 1., 1.]]))**2
        obs = np.transpose(np.array([[5., 35., 200., 1.]]))
        t = np.transpose(np.array([[1., 2., 5., 5.]]))
        ps = np.array([0.564474, 0.620886, 0.000148617, 1.0])

        result = krige.anomaly_detect(preds, vars, obs, t)

        self.assertTrue(np.allclose(result, ps))

    def test_benjamini(self):
        # Example taken from Benjamini and Hochberg 1995, p. 295.
        ps = np.array([0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298,
                       0.0344, 0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590,
                       1.0])
        np.random.shuffle(ps)

        pmax = krige.determine_p_threshold(ps, 0.05)
        self.assertEqual(pmax, 0.0201)

if __name__ == "__main__":
    unittest.main()
