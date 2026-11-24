"""Acquisition of the ISIMIP3b climate data of the v2 channel (daily `tas`, `rsds`, `sfcwind`; monthly `dis`, `qtot` of four GHMs).

The package is outside the code of every phase: it is a data-preparation step with its own configuration
(`config/climate_acquisition.yaml`) and its own manifest (`raw/isimip3b/isimip3b_v2_manifest.json`). Code adapted
from the CRAEI repository carries the provenance header required by A-11; nothing is imported from CRAEI (S-09).
"""
