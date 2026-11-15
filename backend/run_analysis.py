"""Single command for the reproducible SARScope analysis pipeline."""

import argparse
import logging

from src import clean_data, evaluate, model, preprocess, visualize_results

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Prepare inputs, run the baseline, and export results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-preprocessing",
        action="store_true",
        help="Reuse existing study-area crops instead of reading the raw GCOV files.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.skip_preprocessing:
        preprocess.run()
        LOGGER.info("Study-area crops and quality checks complete.")
    clean_data.run()
    LOGGER.info("Radar noise reduction complete.")
    parameters = model.run()
    LOGGER.info("Baseline intensity threshold: %.2f dB", parameters["intensity_threshold_db"])
    report = evaluate.run()
    visualize_results.run()
    LOGGER.info("Candidate new-water area: %.3f km²", report["candidate_new_open_water_km2"])
    LOGGER.info("Results saved to outputs/ and reports/; raw inputs unchanged.")


if __name__ == "__main__":
    main()
