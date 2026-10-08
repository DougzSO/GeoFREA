"""F5 technical_potential: capacity, capacity factor and annual energy per cell and member (M-F5-01 to M-F5-06).

Pure vectorized functions (A-13) in `capacity`, `solar`, `wind_profile`, `power_curve`, `weibull_cf` and `rescale`; the
table schemas, CF models, aggregates and pipeline build on them. No technology name appears in this package (A-04): a
technology selects its CF model by the `cf_model` string of the registry.
"""
