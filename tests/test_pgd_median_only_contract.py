from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path


PGD_DIR = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude"


def load_module(name: str):
    path = PGD_DIR / f"{name}.py"
    if str(PGD_DIR) not in sys.path:
        sys.path.insert(0, str(PGD_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PgdMedianOnlyContractTest(unittest.TestCase):
    def test_contract_names_one_station_aggregation_method_and_three_formulas(self):
        contract = load_module("pgd_contract")
        evaluator = load_module("evaluate_pgd_magnitude")

        self.assertEqual(contract.STATION_AGGREGATION_METHOD, "median")
        self.assertEqual(contract.STATION_AGGREGATION_METHODS, ("median",))
        self.assertEqual(contract.FORMULA_COMPARISON_SCOPE, "formula_only")
        self.assertEqual(contract.METHOD_CONTRACT, "one_station_aggregation_method")
        self.assertEqual(
            contract.FORMULA_NAMES,
            tuple(law.name for law in evaluator.SCALING_LAWS),
        )
        self.assertNotIn("mean", contract.STATION_AGGREGATION_METHODS)
        self.assertNotIn("trimmed-mean", contract.STATION_AGGREGATION_METHODS)

    def test_core_pgd_scripts_share_the_contract(self):
        contract = load_module("pgd_contract")
        evaluator = load_module("evaluate_pgd_magnitude")
        report = load_module("run_pgd_report")
        sensitivity = load_module("run_pgd_sensitivity")
        release = load_module("build_pgd_release_package")

        self.assertIs(evaluator.pgd_contract, contract)
        self.assertEqual(evaluator.STATION_AGGREGATION, contract.STATION_AGGREGATION_METHOD)
        self.assertEqual(report.pgd.STATION_AGGREGATION, contract.STATION_AGGREGATION_METHOD)
        self.assertEqual(sensitivity.pgd.STATION_AGGREGATION, contract.STATION_AGGREGATION_METHOD)
        self.assertEqual(release.STATION_AGGREGATION, contract.STATION_AGGREGATION_METHOD)

    def test_station_estimate_aggregation_exposes_no_method_argument(self):
        evaluator = load_module("evaluate_pgd_magnitude")

        self.assertEqual(
            list(inspect.signature(evaluator.aggregate_station_estimates).parameters),
            ["values"],
        )
        self.assertEqual(evaluator.aggregate_station_estimates([6.0, 7.0, 100.0]), 7.0)
        with self.assertRaises(TypeError):
            evaluator.aggregate_station_estimates([6.0, 7.0, 100.0], "mean")

    def test_legacy_method_named_files_are_only_stale_cleanup_targets(self):
        evaluator = load_module("evaluate_pgd_magnitude")
        report = load_module("run_pgd_report")

        for module in (evaluator, report):
            self.assertFalse(
                hasattr(module, "LEGACY_METHOD_OUTPUTS"),
                "method-named PGD outputs should not be exposed as current or legacy products",
            )
            self.assertFalse(
                hasattr(module, "LEGACY_METHOD_FIGURES"),
                "method-named PGD figures should not be exposed as current or legacy products",
            )
            self.assertTrue(hasattr(module, "STALE_PRE_MEDIAN_CONTRACT_OUTPUTS"))
            self.assertTrue(hasattr(module, "STALE_PRE_MEDIAN_CONTRACT_FIGURES"))
            self.assertTrue(all("method_" in name for name in module.STALE_PRE_MEDIAN_CONTRACT_OUTPUTS))


if __name__ == "__main__":
    unittest.main()
